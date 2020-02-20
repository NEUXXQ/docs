# Copyright 2019 GPflow Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Script to autogenerate .rst files for autodocumentation of classes and modules in GPflow.
To be run by the CI system to update docs.
"""
import inspect
import os

from datetime import datetime
from typing import Any, Callable, List, Set, Tuple
from types import ModuleType

import gpflow

RST_PATH = 'source/'
RST_LEVEL_SYMBOLS = ['=', '-', '~', '"', "'", '^']

SPHINX_CLASS_STRING = '''
{object_name}
{level}

.. autoclass:: {object_name}
   :show-inheritance:
   :members:
'''

SPHINX_MULTIDISPATCH_STRING = '''
{object_name}
{level}

This function uses multiple dispatch, which will depend on the type of argument passed in:

{content}
'''

SPHINX_MULTIDISPATCH_COMPONENT_STRING = '''
.. code-block:: python

    {dispatch_name}( {args} )
    # dispatch to -> {true_name}(...)


.. autofunction:: {true_name}
'''

SPHINX_FUNC_STRING = '''
{object_name}
{level}

.. autofunction:: {object_name}
'''

SPHINX_INCLUDE_MODULE_STRING = '''
{name}
{level}
.. toctree::
   :maxdepth: 1

   {module}/index
'''

SPHINX_FILE_STRING = '''==========
{title}
========

.. THIS IS AN AUTOGENERATED RST FILE
.. GENERATED BY `generate_rst.py`
.. DATE: {date}


{content}
'''


IGNORE_MODULES = {
    'gpflow.covariances.dispatch',
    'gpflow.conditionals.dispatch',
    'gpflow.expectations.dispatch',
    'gpflow.kullback_leiblers.dispatch',
    'gpflow.versions',
}

DATE_STRING = datetime.strftime(datetime.now(), "%d/%m/%y")

def set_global_path(path):
    global RST_PATH
    RST_PATH = path

def is_documentable_module(m: Any) -> bool:
    """Return `True` if m is module to be documented automatically, `False` otherwise.
    """
    return inspect.ismodule(m) and 'gpflow' in m.__name__ and m.__name__ not in IGNORE_MODULES


def is_documentable_component(m: Any) -> bool:
    """Return `True` if a function or class to be documented automatically, `False` otherwise.
    """
    if inspect.isfunction(m):
        return 'gpflow' in m.__module__ and m.__module__ not in IGNORE_MODULES
    elif inspect.isclass(m):
        return 'gpflow' in m.__module__ and m.__module__ not in IGNORE_MODULES
    elif type(m).__name__ == 'Dispatcher':
        return True

    return False


def is_documentable(m: Any) -> bool:
    """Return `True` if a function, class, or module to be documented automatically, else `False`.
    """
    return is_documentable_component(m) or is_documentable_module(m)


def get_component_rst_string(module: ModuleType, component: Callable, level: int) -> str:
    """Get a rst string, to autogenerate documentation for a component (class or function)

    :param module: the module containing the component
    :param component: the component (class or function)
    :param level: the level in nested directory structure
    """
    object_name = f'{module.__name__}.{component.__name__}'

    rst_documentation = ''
    level_underline = RST_LEVEL_SYMBOLS[level]*6
    if inspect.isclass(component):
        rst_documentation = SPHINX_CLASS_STRING.format(
            object_name=object_name, var=component.__name__, level=level_underline)
    elif inspect.isfunction(component):
        rst_documentation = SPHINX_FUNC_STRING.format(
            object_name=object_name, var=component.__name__, level=level_underline)
    elif type(component).__name__ == 'Dispatcher':
        rst_documentation = get_multidispatch_string(component, module,  level_underline)

    return rst_documentation

def get_multidispatch_string(md_component: Callable, module: ModuleType, level: int)-> str:
    """Get the string for a multiple dispatch component. This involves iterating through the
    possible functions and arguments and creating strings for each of these items.

    :param md_component: the multidispatch component (wrapped around functions)
    :param module: the module containing the component
    :param level: the level in nested directory structure
    """
    content_list = []
    dispatch_name = f'{module.__name__}.{md_component.name}'
    for args, fname in md_component.funcs.items():

        arg_names = ', '.join([a.__name__ for a in args])
        alias_name = f'{fname.__module__}.{fname.__name__}'

        string = SPHINX_MULTIDISPATCH_COMPONENT_STRING.format(
            dispatch_name=dispatch_name,
            args=arg_names,
            true_name=alias_name)
        content_list.append(string)
    content = '\n'.join(content_list)
    return SPHINX_MULTIDISPATCH_STRING.format(object_name=dispatch_name,level=level, content=content )


def get_module_rst_string(module: ModuleType, level: int) -> str:
    """Get an rst string, used to autogenerate documentation for a module

    :param module: the module containing the component
    :param level: the level in nested directory structure
    """
    level_underline = RST_LEVEL_SYMBOLS[level]*6
    return SPHINX_INCLUDE_MODULE_STRING.format(
        name=module.__name__, module=module.__name__.split('.')[-1], level=level_underline)


def get_public_attributes(node: Any) -> Any:
    """Get the public attributes ('children') of the current node, accessible from this node.
    """
    return [getattr(node, a) for a in dir(node) if not a.startswith('_')]


def write_to_rst_file(node_name: str, rst_content: List[str]) -> None:
    """Write rst_content to a file, for a certain node.

    :param node_name: name of the node to write to file
    :param rst_content: List of rst strings to write to file
    """
    path = f"{RST_PATH}/{node_name.replace('.', '/')}"
    if not os.path.exists(path):
        os.makedirs(path)

    rst_file = SPHINX_FILE_STRING.format(
        title=node_name, content=''.join(rst_content), date=DATE_STRING)

    path_to_file = path + '/index.rst'
    with open(path_to_file, 'w') as f:
        f.write(rst_file)


def do_visit_module(module: ModuleType, enqueued_items: Set[int]) -> bool:
    """Decide whether to document this module or not, by checking its attributes and deciding
    if there is something worth documenting there

    :param module: module to document
    :param enqueued_items: enqueue the items
    """
    for child in get_public_attributes(module):
        if is_documentable_module(child) and id(child) not in enqueued_items:
            # There is a module we have not visited
            return True
        elif is_documentable_component(child) and id(child) not in enqueued_items and \
                ('__init__' in child.__module__ or module.__name__ in child.__module__):
            # There is a class or function (or alias of them) we have not visited
            return True
    return False


def traverse_module_bfs(queue: List[Tuple[Any, int]], enqueued_items: Set[int]):
    """
    We will traverse the module in the queue to generate .rst files, that will be used by sphinx.
    We do this to avoid having to add new classes or modules to the documentation.
    We traverse the module breadth-first, and check `id` of modules to prevent double documentation
    of same items. We traverse breadth first so that when an alias has been created:
        ie - gpflow.kernels.Matern52 == gpflow.kernels.stationaries.Matern52
    we take the path closest to the root (in this case: goflow.kernels.Matern52)

    :param queue: The queue which contains the module and the starting depth. Usually: [(gpflow, 0)]
    :param enqueued_items: The set tracks objects already in the queue, with `id`: set([id(gpflow)])
    :return: None
    """
    while queue:
        node, level = queue.pop(0)  # currently using a list as a queue (not great)

        if not hasattr(node, '__name__'):
            continue

        if is_documentable_module(node):

            rst_components, rst_modules = [], []
            for child in get_public_attributes(node):

                if id(child) in enqueued_items:
                    continue

                if is_documentable_component(child):
                    rst_components.append(get_component_rst_string(node, child, level))
                    enqueued_items.add(id(child))

                elif is_documentable_module(child):
                    if do_visit_module(child, enqueued_items):
                        rst_modules.append(get_module_rst_string(child, level))
                        queue.append((child, level+1))
                        enqueued_items.add(id(child))

            rst_content = '\n'.join(rst_components + rst_modules)
            if rst_content:
                write_to_rst_file(node.__name__, rst_content)


if __name__ == '__main__':
    traverse_module_bfs([(gpflow, 0)], set([id(gpflow)]))
