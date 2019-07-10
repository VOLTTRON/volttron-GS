# This is a namespace package; do not add anything else to this file.
__path__ = __import__('pkgutil').extend_path(__path__, __name__)
__import__('pkg_resources').declare_namespace(__name__)