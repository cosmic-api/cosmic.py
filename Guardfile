from livereload.task import Task
from livereload.compiler import shell

make_docs = "source .tox/py27/bin/activate; cd docs; make clean; make html"

Task.add('docs/source/*.rst', shell('make docs'))
Task.add('cosmic/*.py', shell('make docs'))
