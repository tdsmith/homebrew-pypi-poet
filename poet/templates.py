from textwrap import dedent

from jinja2 import Environment

from .util import dash_to_studly


env = Environment(trim_blocks=True)
env.filters["dash_to_studly"] = dash_to_studly


FORMULA_TEMPLATE = env.from_string(dedent("""\
    class {{ package.name|dash_to_studly }} < Formula
      include Language::Python::Virtualenv

      desc "Shiny new formula"
      homepage "{{ package.homepage }}"
      url "{{ package.url }}"
      sha256 "{{ package.checksum }}"

      depends_on "{{ python }}"
    {% for depend in extra_depends %}
      depends_on "{{ depend }}"
    {% endfor %}

    {% if resources %}
    {%   for resource in resources %}
    {%     include ResourceTemplate %}


    {%   endfor %}
    {% endif %}
      def install
    {% if python == "python3" %}
        virtualenv_create(libexec, "python3")
    {% endif %}
        virtualenv_install_with_resources
      end

      test do
        false
      end
    end
    """))


RESOURCE_TEMPLATE = env.from_string("""\
  resource "{{ resource.name }}" do
    url "{{ resource.url }}"
    {{ resource.checksum_type }} "{{ resource.checksum }}"
  end
""")


def template_from_file(path):
    with open(path) as file_:
      return env.from_string(file_.read())
