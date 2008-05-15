`cmd2` is a tool for writing command-line interactive applications.  It is based on the Python Standard Library's `cmd` module, and can be used anyplace `cmd` is used simply by importing `cmd2` instead.

`cmd2` provides the following features, in addition to those already existing in `cmd`:

- Searchable command history
- Load commands from file, save to file, edit commands in file
- Multi-line commands
- Case-insensitive commands
- Special-character shortcut commands (beyond cmd's "@" and "!")
- Settable environment parameters
- Parsing commands with flags

Instructions for implementing each feature follow.

- Searchable command history

    All commands will automatically be tracked in the session's history, unless the command is listed in Cmd's excludeFromHistory attribute.  
    The history is accessed through the `history`, `list`, and `run` commands 
    (and their abbreviations: `hi`, `li`, `l`, `r`).
    If you wish to exclude some of your custom commands from the history, append their names
    to the list at Cmd.ExcludeFromHistory.

- Load commands from file, save to file, edit commands in file

    Type `help load`, `help save`, `help edit` for details.
  
- Multi-line commands

    Any command accepts multi-line input when its name is listed in `Cmd.multilineCommands`.
    The program will keep expecting input until a line ends with any of the characters 
    in `Cmd.terminators` .  The default terminators are `;` and `/n` (empty newline).
    
- Case-insensitive commands

    All commands are case-insensitive, unless `Cmd.caseInsensitive` is set to `False`.
  
- Special-character shortcut commands (beyond cmd's "@" and "!")

    To create a single-character shortcut for a command, update `Cmd.shortcuts`.
  
- Settable environment parameters

    To allow a user to change an environment parameter during program execution, 
    append the parameter's name to `Cmd.settable`.
    
- Parsing commands with `optparse` options (flags) 

    ::
    
        @options([make_option('-m', '--myoption', action="store_true", help="all about my option")])
        def do_myfunc(self, arg, opts):
            if opts.myoption:
                ...
            
    See Python standard library's `optparse` documentation: http://docs.python.org/lib/optparse-defining-options.html
    
- Catherine Devlin, http://catherinedevlin.blogspot.com

cmd2 can be installed with `easy_install cmd2`

Cheese Shop page: http://pypi.python.org/pypi/cmd2

Example cmd2 application (cmd2_example.py) ::

    from cmd2 import Cmd, make_option, options

    class CmdLineApp(Cmd):
        multilineCommands = ['orate']
        Cmd.shortcuts.update({'&': 'speak'})
        maxrepeats = 3
        Cmd.settable.append('maxrepeats')       
    
        @options([make_option('-p', '--piglatin', action="store_true", help="atinLay"),
                  make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE"),
                  make_option('-r', '--repeat', type="int", help="output [n] times")
                 ])
        def do_speak(self, arg, opts=None):
            """Repeats what you tell me to."""
            arg = ' '.join(arg)
            if opts.piglatin:
                arg = '%s%say' % (arg[1:], arg[0])
            if opts.shout:
                arg = arg.upper()            
            repetitions = opts.repeat or 1
            for i in range(min(repetitions, self.maxrepeats)):
                self.stdout.write(arg)
                self.stdout.write('\n')
                # self.stdout.write is better than "print", because Cmd can be 
                # initialized with a non-standard output destination
        
        do_say = do_speak     # now "say" is a synonym for "speak"
        do_orate = do_speak   # another synonym, but this one takes multi-line input
    
    app = CmdLineApp()
    app.cmdloop()    

Sample session using the above code ::

    c:\cmd2>python cmd2_example.py
    (Cmd) speak softly
    softly    
    (Cmd) speak --piglatin softly
    oftlysay
    (Cmd) speak -psr 2 softly
    OFTLYSAY
    OFTLYSAY
    (Cmd) speak --repeat 1000000 softly
    softly
    softly
    softly
    (Cmd) show maxrepeats
    maxrepeats: 3
    (Cmd) set maxrepeats 5
    maxrepeats - was: 3
    now: 5
    (Cmd) speak --repeat 1000000 softly
    softly
    softly
    softly
    softly
    softly
    (Cmd) orate blah blah
    > blah
    > and furthermore
    > blah
    >
    blah blah blah and furthermore blah
    (Cmd) &greetings
    greetings 
    (Cmd) history
    -------------------------[1]
    speak softly
    -------------------------[2]
    speak --piglatin softly
    -------------------------[3]
    speak -psr 2 softly
    -------------------------[4]
    speak --repeat 1000000 softly
    -------------------------[5]
    show maxrepeats
    -------------------------[6]
    set maxrepeats 5
    -------------------------[7]
    speak --repeat 1000000 softly
    -------------------------[8]
    orate blah blah
    blah
    and furthermore
    blah
    
    -------------------------[9]
    &greetings  
    (Cmd) run
    orate blah blah
    blah
    and furthermore
    blah
    
    blah blah blah and furthermore blah
    (Cmd) run 3
    speak -psr 2 softly
    OFTLYSAY
    OFTLYSAY
    (Cmd) history maxrepeats
    -------------------------[5]
    set maxrepeats
    -------------------------[6]
    set maxrepeats 5
    (Cmd)
