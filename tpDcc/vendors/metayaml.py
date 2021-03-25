import os
import jinja2
import yaml
import six
from copy import deepcopy
from collections import MutableMapping, defaultdict, Iterable, Mapping
from glob import glob
import yaml.constructor
try:
    from collections import OrderedDict
except ImportError:
    OrderedDict = None

if six.PY2:
    getcwd = lambda filename: os.getcwdu() if isinstance(filename, unicode) else os.getcwd()
else:
    getcwd = lambda filename: os.getcwd()

if OrderedDict:
    class OrderedDictYAMLLoader(yaml.Loader):
        """
        A YAML loader that loads mappings into ordered dictionaries.
        """

        def __init__(self, *args, **kwargs):
            yaml.Loader.__init__(self, *args, **kwargs)

            self.add_constructor('tag:yaml.org,2002:map', type(self).construct_yaml_map)
            self.add_constructor('tag:yaml.org,2002:omap', type(self).construct_yaml_map)

        def construct_yaml_map(self, node):
            data = OrderedDict()
            yield data
            value = self.construct_mapping(node)
            data.update(value)

        def construct_mapping(self, node, deep=False):
            if isinstance(node, yaml.MappingNode):
                self.flatten_mapping(node)
            else:
                raise yaml.constructor.ConstructorError(None, None,
                                                        'expected a mapping node, but found %s' % node.id,
                                                        node.start_mark)

            mapping = OrderedDict()
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                except TypeError as exc:
                    raise yaml.constructor.ConstructorError('while constructing a mapping',
                                                            node.start_mark,
                                                            'found unacceptable key (%s)' % exc, key_node.start_mark)
                value = self.construct_object(value_node, deep=deep)
                mapping[key] = value
            return mapping


class MetaYamlException(Exception):
    pass


class FileNotFound(MetaYamlException):
    pass


def _to_str(value):
    if six.PY2:
        if isinstance(value, unicode):
            return value
    return str(value)


class MetaYaml(object):
    eager_brackets = "${", "}"
    lazy_brackets = "$(", ")"

    DEL_MARKER = "${__del__}"
    DEL_ALL_MARKER = "${__del_all__}"
    EXTEND_MARKER = "${__extend__}"
    INHERIT_MARKER = "${__inherit__}"

    @staticmethod
    def cp(source, *args, **kwargs):
        if isinstance(source, Mapping):
            result = deepcopy(source)
            for arg in args:
                result.update(arg)
            result.update(kwargs)
            return result
        elif isinstance(source, (list, tuple)):
            result = list(source)
            result.extend(args)
            return result
        raise MetaYamlException("cp method support only dict and list as source")

    def __init__(self, yaml_file, defaults=None, extend_key_word="extend",
                 ignore_errors=False, ignore_not_existed_files=False,
                 disable_order_dict=False):
        """
          Reads and process yaml config files

          :param yaml_file
          :type  yaml_file      str or list[str]
          :param defaults       Dictionary with default values which can be use during parsing yaml files
          :param extend_key_word  The name of section with list of included files
          :param ignore_errors  Do not rise exception when value can't be rendered
          :param ignore_not_existed_files Do not rise exception if the file not found
          :param disable_order_dict  The dict type is used if it is true and OrderedDict otherwise
        """

        self._extend_key_word = extend_key_word
        self.disable_order_dict = disable_order_dict or (not OrderedDict)
        self.data = defaults or {}
        if not disable_order_dict:
            self.data = OrderedDict(self.data)
        self.data["cp"] = self.cp

        self.cache_template = defaultdict(lambda: {})
        self.ignore_errors = ignore_errors
        self.ignore_not_existed_files = ignore_not_existed_files
        self.processed_files = set()

        if isinstance(yaml_file, six.string_types):
            yaml_file = [yaml_file]
        else:
            assert isinstance(yaml_file, Iterable), "yaml_file should be string or list of strings"

        files = self.extend_filename(yaml_file)
        for filename in files:
            self.load(filename, self.data)

        self.substitute(self.data, self.data, (os.path.basename(files[0]), ), False)
        self.data.pop(self._extend_key_word, None)
        if self.data["cp"] == self.cp:
            del self.data["cp"]

    def extend_filename(self, file_list, path=None):
        files = []
        for filename in file_list:
            if not os.path.isabs(filename):
                if not path:
                    path = getcwd(filename)

                filename = os.path.join(path, filename)

            found_files = glob(filename)
            if not self.ignore_not_existed_files and not found_files:
                raise FileNotFound("File %s not found" % filename)
            found_files.sort()
            files.extend(found_files)

        return files

    def load(self, path, data):
        if path in self.processed_files:
            return data  # file was already processed

        self.processed_files.add(path)
        basename = (os.path.basename(path), )
        file_dir = os.path.dirname(path)

        with open(path, "rb") as f:
            loader = yaml.Loader if self.disable_order_dict else OrderedDictYAMLLoader
            file_data = yaml.load(f, loader) or {}

        extends = file_data.get(self._extend_key_word, [])
        if extends:
            extends = self.substitute(extends, data, basename + (self._extend_key_word, ), eager=True)
            if isinstance(extends, six.string_types):
                extends = [extends]

            if not isinstance(extends, Iterable):
                raise MetaYamlException("The value of %s should be list of string or string" %
                                        self._path_to_str([basename, self._extend_key_word]))

            for file_name in extends:
                if not isinstance(file_name, six.string_types):
                    raise MetaYamlException("The value of %s should be list of string or string" %
                                            self._path_to_str([basename, self._extend_key_word]))

            for file_name in self.extend_filename(extends, file_dir):
                try:
                    self.load(file_name, data)
                except IOError as e:
                    raise FileNotFound("Open file %s error from %s: %s" % (file_name, path, e))

        self._merge(data, file_data, data, tuple())
        self.substitute(data, data, basename, eager=True)

        return data

    def substitute(self, value, data, path, eager):
        if isinstance(value, MutableMapping):
            active_dict = value
            inherit = value.pop(self.INHERIT_MARKER, None)
            if inherit:
                target_dict = self.eval_value("%s%s%s" % (self.eager_brackets[0], inherit, self.eager_brackets[1]),
                                              path + ("__inherit__", ), data, eager)
                if not isinstance(active_dict, MutableMapping):
                    raise MetaYamlException("%s value must be dict for path: %s" % (
                        self.INHERIT_MARKER, self._path_to_str(path)))
                dict_snapshot = active_dict.copy()
                active_dict.clear()
                active_dict.update(deepcopy(target_dict))
                self._merge(active_dict, dict_snapshot, data, path)
            else:
                dict_snapshot = active_dict.copy()

                for key, val in six.iteritems(dict_snapshot):
                    new_path = path + (_to_str(key), )
                    new_key = self.eval_value(key, new_path, data, eager)
                    if new_key != key:
                        del active_dict[key]
                    active_dict[new_key] = self.substitute(val, data, new_path, eager)

        elif isinstance(value, list):
            for key in range(len(value)):
                value[key] = self.substitute(value[key], data, path + (_to_str(key), ), eager)
        elif isinstance(value, six.string_types):
            value = self.eval_value(value, path, data, eager)

        return value

    @staticmethod
    def _path_to_str(path):
        def to_str(p):
            if isinstance(p, six.string_types):
                # noinspection PyTypeChecker
                return "." + p
            else:
                return "[%s]" % (p,)

        l = (to_str(p) for p in path)
        s = "".join(l)
        if s.startswith("."):
            s = s[1:]
        return s

    # noinspection PyUnresolvedReferences
    def eval_value(self, val, path, data, eager):
        if not isinstance(val, six.string_types):
            return val

        brackets = self.eager_brackets if eager else self.lazy_brackets
        if brackets[0] not in val:
            return val

        # disable force string conversion
        original_to_string = jinja2.runtime.to_string
        jinja2.runtime.to_string = lambda x: x

        cache = self.cache_template[eager]
        t = cache.get(val)
        undefined = jinja2.Undefined if self.ignore_errors else jinja2.StrictUndefined
        if t is None:
            try:
                t = jinja2.Template(val, variable_start_string=brackets[0], variable_end_string=brackets[1],
                                    undefined=undefined)
            except Exception as e:
                if not self.ignore_errors:
                    raise MetaYamlException("Template compiling error of key: %s, value: %s, error: %s" % (
                        self._path_to_str(path), val, e))
            cache[val] = t
        try:
            data_str_key = {_to_str(k): v for k, v in six.iteritems(data)}
            rendered = list(t.root_render_func(t.new_context(data_str_key)))
            if len(rendered) == 1:
                if isinstance(rendered[0], undefined) and not self.ignore_errors:
                    raise MetaYamlException("Incorrect template for path: %s, value: %s" % (
                        self._path_to_str(path), val))
                result = rendered[0]
            else:
                rendered = [_to_str(rr) for rr in rendered]
                result = six.u("").join(rendered)
        except MetaYamlException:
            raise
        except Exception as e:
            result = val
            if not self.ignore_errors:
                raise MetaYamlException("Render template error of %s, %s: %s" % (self._path_to_str(path), val, e))
        finally:
            jinja2.runtime.to_string = original_to_string

        if isinstance(result, six.string_types):
            for t in [int, float]:
                try:
                    result = t(result)
                    break
                except (ValueError, TypeError):
                    pass

        return result

    def _merge(self, a, b, data, path):
        for key, b_value in six.iteritems(b):
            if key == self.DEL_MARKER:
                new_value = self.substitute(b_value, data, path + (str(key), ), True)
                if isinstance(new_value, Iterable) and not isinstance(new_value, six.string_types):
                    for v in new_value:
                        a.pop(v, None)
                else:
                    a.pop(new_value, None)
            elif key == self.DEL_ALL_MARKER:
                a.clear()

        for key, b_value in six.iteritems(b):
            if key in (self.DEL_MARKER, self.DEL_ALL_MARKER):
                continue
            a_value = a.get(key)
            if isinstance(a_value, MutableMapping) and isinstance(b_value, MutableMapping):
                self._merge(a[key], b_value, data, path + (str(key), ))
            elif (isinstance(a_value, list) and isinstance(b_value, MutableMapping) and
                  len(b_value) == 1 and self.EXTEND_MARKER in b_value):
                extend = b_value[self.EXTEND_MARKER]
                if not isinstance(extend, list):
                    raise MetaYamlException("The value of %s.%s must be list" %
                                            (self._path_to_str(path), self.EXTEND_MARKER))

                a[key].extend(extend)
            else:
                a[key] = b_value
        return a


def read(yaml_file, defaults=None, extend_key_word="extend", ignore_errors=False,
         ignore_not_existed_files=False, disable_order_dict=False):
    """
      Reads and process yaml config files

      :param yaml_file
      :type  yaml_file      str or list[str]
      :param defaults       Dictionary with default values which can be use during parsing yaml files
      :param extend_key_word  The name of section with list of included files
      :param ignore_errors  Do not rise exception when value can't be rendered
      :param ignore_not_existed_files Do not rise exception if the file not found
      :param disable_order_dict  The dict type is used if it is true and OrderDict otherwise
    """
    m = MetaYaml(yaml_file, defaults, extend_key_word, ignore_errors, ignore_not_existed_files, disable_order_dict)
    return m.data
