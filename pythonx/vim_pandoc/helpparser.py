from subprocess import Popen, PIPE
import re
from collections import namedtuple
from itertools import chain
import argparse

PandocOption = namedtuple('PandocOption', ['names', 'arg', 'optional_arg'])

class PandocInfo(object):
    def __init__(self, pandoc='pandoc'):
        self.pandoc = pandoc
        self.update()

    def __raw_output(self, cmd, pattern=None):
        data = Popen([self.pandoc, cmd], stdout=PIPE).communicate()[0]
        if pattern:
            return re.search(pattern, data, re.DOTALL).group(1)
        else:
            return data

    def update(self):
        self.version = self.get_version()
        self.options = self.get_options()
        self.extensions = self.get_extensions()
        self.input_formats = self.get_input_formats()
        self.output_formats = self.get_output_formats()

    def get_version(self):
        return self.__raw_output('--version', pattern=b'pandoc (\d+\.\d+)').decode()

    def get_options(self):
        # first line describes pandoc usage
        data = self.__raw_output('--help').splitlines()[1:]
        data = [l.strip() for l in data]
        # options from --trace onwards are not meaningful for us
        cutoff = data.index(b'--trace')
        data = data[:cutoff]

        options = []

        for line in data:
            # TODO: simplify if possible
            if re.search(b',', line): # multiple variant options
                if re.search(b'(?<![a-z])(?<!-)-(?!-)', line):
                    if re.search(b'\[', line):
                        optional = True
                    else:
                        optional = False
                    opts = re.findall(b'-+([a-zA-Z-]+)[[ =]', line)
                    if opts:
                        options.append(PandocOption(opts, True, optional))

                else:
                    opts = re.findall(b'--([a-z-]+)', line)
                    if opts:
                        options.append(PandocOption(opts, False, False))
            else:
                if re.search(b'=', line): # take arguments
                    if re.search(b'\[=', line): # arguments are optional
                        optional = re.findall(b'--([a-z-]+)\[=', line)
                        if optional:
                            options.append(PandocOption(optional, True, True))
                    else:
                        optarg_opts = re.findall(b'-+([a-zA-Z-]+)[ =][A-Za-z]+', line)
                        if optarg_opts:
                            options.append(PandocOption(optarg_opts, True, False))
                else: # flags
                    flag_opts = re.findall(b'-+([a-z-]+(?![=]))', line)
                    if flag_opts:
                        options.append(PandocOption(flag_opts, False, False))

        return options

    def get_options_list(self):
        return list(chain.from_iterable([v.names for v in self.options]))

    def get_extensions(self):
        data = self.__raw_output('--list-extensions').\
            replace(b' +', b'').replace(b' -', b'')
        return [i.decode() for i in data.splitlines()]

    def get_input_formats(self):
        data = self.__raw_output('--list-input-formats')
        return [i.decode() for i in data.splitlines()]

    def get_output_formats(self):
        data = self.__raw_output('--list-output-formats')
        return [i.decode() for i in data.splitlines()]

    def is_valid_output_format(self, identifier):
        if not identifier.startswith("markdown") and identifier in self.output_formats:
            return True
        elif identifier.startswith("markdown"):
            return re.match(identifier+"(([+-]("+"|".join(self.extensions)+"))+)?$", identifier)

    def build_argument_parser(self):
        def wrap_flag(flag):
            if len(flag) == 1:
                return "-" + flag
            else:
                return "--" + flag

        parser = argparse.ArgumentParser()
        parser.add_argument('output_format')
        for opt in self.options:
            flags = [wrap_flag(f.decode()) for f in opt.names]
            extra = {}
            extra['action'] = 'store_true' if not opt.arg else 'store'
            # some options can be given several times
            if any(map(lambda x: x.isupper() and x != b'T' or x == b'bibliography', opt.names)):
                extra['action'] = 'append'

            if opt.arg:
                extra['nargs'] = '?' if opt.optional_arg else 1
            parser.add_argument(*flags, **extra)
        return parser
