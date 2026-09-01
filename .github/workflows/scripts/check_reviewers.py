"""Check whether the required approvals have been met from REQUIRED_REVIEWERS to allow the PR to
merge. Returns exit code 0 if approvals are met, 1 on error, and 2 if approvals are not met."""

import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Final, NamedTuple

import requests

EXPECTED_TOTAL_REVIEWS: Final[int] = 2


class ReqReviewerRule(NamedTuple):
    """A single rule (line) from the REQUIRED_REVIEWERS file."""

    pattern: str
    owners: list[str]


def get_changed_files(repo: str, pr_number: int, token: str) -> list[str]:
    """Get the filenames of the files that have been changed in the PR."""
    files = requests.get(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files",
        headers={"Authorization": f"token {token}"},
    ).json()

    return [f["filename"] for f in files]


def get_approved_reviewers(repo: str, pr_number: int, token: str) -> set[str]:
    """Get the set of usernames of the reviewers that have approved the PR."""
    reviews = requests.get(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
        headers={"Authorization": f"token {token}"},
    ).json()

    return {r["user"]["login"] for r in reviews if r["state"] == "APPROVED"}


def parse_required_reviewers_file(path: Path) -> list[ReqReviewerRule]:
    """Parse the REQUIRED_REVIEWERS file to get a record of every rule in it."""
    rules = []
    with path.open("r") as f:
        for line in f:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue

            parts = stripped_line.split()
            pattern = parts[0]
            owners = [o.lstrip("@") for o in parts[1:]]
            rules.append(ReqReviewerRule(pattern=pattern, owners=owners))

    return rules


def determine_required_reviewers(
    rules: list[ReqReviewerRule], filenames: list[str], pr_author: str
) -> set[str]:
    """Determine the set of required reviewers for the provided set of files.

    The last matched rule for a particular file overrides previous rules. The PR author is
    excluded."""
    required = set()

    for file in filenames:
        last_match_owners = set()

        for rule in rules:
            if fnmatch.fnmatch(file, rule.pattern):
                last_match_owners = rule.owners

        if last_match_owners:
            required.update(last_match_owners)

    required.discard(pr_author)
    return required


def build_reviewer_comment(required: set[str], approved: set[str], is_draft: bool) -> str:
    """Get the text for the PR comment based on the number of approvals from required reviewers."""
    required_list = ", ".join(sorted(required))
    approved_list = ", ".join(sorted(approved)) or "_None_"

    if is_draft:
        return (
            "📝 **Draft PR - suggested reviewers**\n\n"
            "At least one of the following must approve this PR once it leaves draft:\n\n"
            f"{required_list}\n\n"
            f"Please get {EXPECTED_TOTAL_REVIEWS} approvals in total before merging, if possible."
        )

    required_reviewers_satisfied = bool(approved & required)
    total_reviewers_satisfied = len(approved) >= EXPECTED_TOTAL_REVIEWS

    if required_reviewers_satisfied and total_reviewers_satisfied:
        return (
            "✅ **Required reviewers satisfied**\n\n"
            "✅ **There is no requirement for further approvals**"
        )

    if required_reviewers_satisfied:
        return (
            "✅ **Required reviewers satisfied**\n\n"
            f"🤔 **Please get {EXPECTED_TOTAL_REVIEWS} approvals in total before merging, "
            "if possible**"
        )

    if total_reviewers_satisfied:
        return (
            "❌ **Missing required reviewer approval**\n\n"
            "At least one of the following must approve this PR:\n\n"
            f"{required_list}\n\nCurrently approved by:\n\n{approved_list}\n\n"
            "✅ **Total reviewers expectations have been met**"
        )

    return (
        "❌ **Missing required reviewer approval**\n\n"
        "At least one of the following must approve this PR:\n\n"
        f"{required_list}\n\nCurrently approved by:\n\n{approved_list}\n\n"
        f"❌ **Please get {EXPECTED_TOTAL_REVIEWS} approvals in total before merging, if possible**"
    )


def post_or_update_comment(
    repo: str, pr_number: str, token: str, comment_marker: str, comment_body: str
) -> None:
    """Post a new comment on the repo or update the existing one, determining whether the comment is
    already present by searching for a comment with the provided marker."""
    headers = {"Authorization": f"token {token}"}

    # Find existing bot comment
    comments = requests.get(
        f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments", headers=headers
    ).json()

    existing = None
    for c in comments:
        if c["user"]["type"] == "Bot" and comment_marker in c["body"]:
            existing = c
            break

    # Create or update comment
    body_with_marker = comment_marker + "\n" + comment_body
    if existing:
        requests.patch(existing["url"], headers=headers, json={"body": body_with_marker})
    else:
        requests.post(
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
            headers=headers,
            json={"body": body_with_marker},
        )


if __name__ == "__main__":
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    is_draft = os.environ["PR_IS_DRAFT"] == "true"

    with Path(os.environ["GITHUB_EVENT_PATH"]).open("r") as f:
        event = json.load(f)
    pr_number = event["pull_request"]["number"]
    pr_author = event["pull_request"]["user"]["login"]

    changed_files = get_changed_files(repo, pr_number, token)
    approved_reviewers = get_approved_reviewers(repo, pr_number, token)

    rules = parse_required_reviewers_file(Path(".github/REQUIRED_REVIEWERS"))
    required_reviewers = determine_required_reviewers(rules, changed_files, pr_author)

    marker = "<!-- required-reviewers-check -->"
    comment_body = build_reviewer_comment(required_reviewers, approved_reviewers, is_draft)
    post_or_update_comment(repo, pr_number, token, marker, comment_body)

    if bool(approved_reviewers & required_reviewers):
        print("Valid approval found")
        sys.exit(0)
    else:
        print("Missing required approval")
        sys.exit(2)
