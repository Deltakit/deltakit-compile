{{ fullname | escape | underline }}

.. automodule:: {{ fullname }}
{% set api = api_modules[fullname] %}
{%- if api.modules %}

.. rubric:: Modules

.. autosummary::
   :toctree:
{% for item in api.modules %}
   ~{{ item }}
{%- endfor %}
{%- endif %}
{%- if api.classes %}

.. rubric:: Classes

.. autosummary::
   :toctree:
{% for item in api.classes %}
   ~{{ fullname }}.{{ item }}
{%- endfor %}
{%- endif %}
{%- if api.functions %}

.. rubric:: Functions

.. autosummary::
   :toctree:
{% for item in api.functions %}
   ~{{ fullname }}.{{ item }}
{%- endfor %}
{%- endif %}
{%- if api.links %}

.. rubric:: Re-exported

.. autosummary::
{% for item in api.links %}
   ~{{ item }}
{%- endfor %}
{%- endif %}
{%- if api.data %}

.. rubric:: Attributes
{% for item in api.data %}
.. autodata:: {{ fullname }}.{{ item }}
{%- endfor %}
{%- endif %}
