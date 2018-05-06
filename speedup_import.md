# Speedup Import

## Assumptions

I created a simple script to run a command 20 times and calculate
the average clock time for each run of the command. This script requires
some unix tools, including the gnu flavor of the `time` command. This script
can is called `mtime.sh` and is included in this branch.

These tests were all run on my 2015 MacBook Pro with a 3.1 GHz Intel Core i7
and 16GB of memory.


## Baseline measurement

First let's see how long it takes to start up python. The longish path here
ensures we aren't measuring the time it takes the pyenv shims to run:
```
$./mtime.sh ~/.pyenv/versions/cmd2-3.6/bin/python -c ""
100 iterations
average: real 0.028 user 0.020 sys 0.000
```


## Initial measurement

From commit fbbfe256, which has `__init.py__` importing `cmd2.cmd2.Cmd`
and a bunch of other stuff, we get:
```
$ ./mtime.sh ~/.pyenv/versions/cmd2-3.6/bin/python -c "import cmd2"
100 iterations
average: real 0.140 user 0.100 sys 0.030
```

From the baseline and this initial measurement, we infer it takes ~110 ms
to import the `cmd2` module.


## Defer unittest

In commit 8bc2c37a we defer the import of `unittest` until we need it to
test a transcript.
```
$./mtime.sh ~/.pyenv/versions/cmd2-3.6/bin/python -c "import cmd2"
100 iterations
average: real 0.131 user 0.091 sys 0.030
```


## Defer InteractiveConsole from code

In commit 6e49661f we defer the import of `InteractiveConsole` until the user
wants to run the `py` command.
```
$ ./mtime.sh ~/.pyenv/versions/cmd2-3.6/bin/python -c "import cmd2"
100 iterations
average: real 0.131 user 0.090 sys 0.030
```

## Defer atexit, codes, signal, tempfile, copy

In commit a479fa94 we defer 5 imports: atexit, codecs, signal, tempfile, and copy.
```
$ ./mtime.sh ~/.pyenv/versions/cmd2-3.6/bin/python -c "import cmd2"100 iterations
average: real 0.120 user 0.081 sys 0.021
```
