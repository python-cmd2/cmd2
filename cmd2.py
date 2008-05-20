"""Variant on standard library's cmd with extra features.

To use, simply import cmd2.Cmd instead of cmd.Cmd; use precisely as though you
were using the standard library's cmd, while enjoying the extra features.

Searchable command history (commands: "hi", "li", "run")
Load commands from file, save to file, edit commands in file
Multi-line commands
Case-insensitive commands
Special-character shortcut commands (beyond cmd's "@" and "!")
Settable environment parameters
Parsing commands with `optparse` options (flags)
Redirection to file with >, >>; input from file with <

- Catherine Devlin, Jan 03 2008 - catherinedevlin.blogspot.com

CHANGES:
As of 0.3.0, options should be specified as `optparse` options.  See README.txt.
flagReader.py options are still supported for backward compatibility
"""
import cmd, re, os, sys, optparse, subprocess, tempfile
from optparse import make_option

class OptionParser(optparse.OptionParser):
    def exit(self, status=0, msg=None):
        self.values._exit = True
        if msg:
            print msg

    def error(self, msg):
        """error(msg : string)

        Print a usage message incorporating 'msg' to stderr and exit.
        If you override this in a subclass, it should not return -- it
        should either exit or raise an exception.
        """
        raise
        
def options(option_list):
    def option_setup(func):
        optionParser = OptionParser()
        for opt in option_list:
            optionParser.add_option(opt)
        optionParser.set_usage("%s [options] arg" % func.__name__.strip('do_'))
        def newFunc(instance, arg):
            try:
                opts, arg = optionParser.parse_args(arg.split())
                arg = ' '.join(arg)
            except (optparse.OptionValueError, optparse.BadOptionError,
                    optparse.OptionError, optparse.AmbiguousOptionError,
                    optparse.OptionConflictError), e:
                print e
                optionParser.print_help()
                return
            if hasattr(opts, '_exit'):
                return None
            result = func(instance, arg, opts)                            
            return result
        newFunc.__doc__ = '%s\n%s' % (func.__doc__, optionParser.format_help())
        return newFunc
    return option_setup

class PasteBufferError(EnvironmentError):
    if sys.platform[:3] == 'win':
        errmsg = """Redirecting to or from paste buffer requires pywin32
to be installed on operating system.
Download from http://sourceforge.net/projects/pywin32/"""
    else:
        errmsg = """Redirecting to or from paste buffer requires xclip 
to be installed on operating system.
On Debian/Ubuntu, 'sudo apt-get install xclip' will install it."""        
    def __init__(self):
        Exception.__init__(self, self.errmsg)

'''check here if functions exist; otherwise, stub out'''
pastebufferr = """Redirecting to or from paste buffer requires %s
to be installed on operating system.
%s"""
if subprocess.mswindows:
    try:
        import win32clipboard
        def getPasteBuffer():
            win32clipboard.OpenClipboard(0)
            try:
                result = win32clipboard.GetClipboardData()
            except TypeError:
                result = ''  #non-text
            win32clipboard.CloseClipboard()
            return result            
        def writeToPasteBuffer(txt):
            win32clipboard.OpenClipboard(0)
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(txt)
            win32clipboard.CloseClipboard()        
    except ImportError:
        def getPasteBuffer():
            raise OSError, pastebufferr % ('pywin32', 'Download from http://sourceforge.net/projects/pywin32/')
        setPasteBuffer = getPasteBuffer
else:
    can_clip = False
    try:
        subprocess.check_call('xclip -o -sel clip', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        can_clip = True
    except AttributeError:  # check_call not defined, Python < 2.5
        teststring = 'Testing for presence of xclip.'
        #import pdb; pdb.set_trace()
        xclipproc = subprocess.Popen('xclip -sel clip', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        xclipproc.stdin.write(teststring)
        xclipproc.stdin.close()
        xclipproc = subprocess.Popen('xclip -o -sel clip', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)        
        if xclipproc.stdout.read() == teststring:
            can_clip = True
    except (subprocess.CalledProcessError, OSError):
        pass
    if can_clip:    
        def getPasteBuffer():
            xclipproc = subprocess.Popen('xclip -o -sel clip', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
            return xclipproc.stdout.read()
        def writeToPasteBuffer(txt):
            xclipproc = subprocess.Popen('xclip -sel clip', shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
            xclipproc.stdin.write(txt)
            xclipproc.stdin.close()
    else:
        def getPasteBuffer():
            raise OSError, pastebufferr % ('xclip', 'On Debian/Ubuntu, install with "sudo apt-get install xclip"')
        setPasteBuffer = getPasteBuffer
                
class Cmd(cmd.Cmd):
    caseInsensitive = True
    multilineCommands = []
    continuationPrompt = '> '    
    shortcuts = {'?': 'help', '!': 'shell', '@': 'load'}
    excludeFromHistory = '''run r list l history hi ed li eof'''.split()   
    defaultExtension = 'txt'
    defaultFileName = 'command.txt'
    editor = os.environ.get('EDITOR')
    if not editor:
        if sys.platform[:3] == 'win':
            editor = 'notepad'
        else:
            for editor in ['gedit', 'kate', 'vim', 'emacs', 'nano', 'pico']:
                if os.system('which %s' % (editor)):
                    break
            
    settable = ['prompt', 'continuationPrompt', 'defaultFileName', 'editor', 'caseInsensitive']
    terminators = ';\n'
    _TO_PASTE_BUFFER = 1
    def do_cmdenvironment(self, args):
        self.stdout.write("""
        Commands are %(casesensitive)scase-sensitive.
        Commands may be terminated with: %(terminators)s
        Settable parameters: %(settable)s
        """ % 
        { 'casesensitive': ('not ' and self.caseInsensitive) or '',
          'terminators': ' '.join(self.terminators),
          'settable': ' '.join(self.settable)
        })
        
    def do_help(self, arg):
        cmd.Cmd.do_help(self, arg)
        try:
            fn = getattr(self, 'do_' + arg)
            if fn and fn.optionParser:
                fn.optionParser.print_help(file=self.stdout)
        except AttributeError:
            pass
        
    def __init__(self, *args, **kwargs):        
        cmd.Cmd.__init__(self, *args, **kwargs)
        self.history = History()
        
    def do_shortcuts(self, args):
        """Lists single-key shortcuts available."""
        result = "\n".join('%s: %s' % (sc[0], sc[1]) for sc in self.shortcuts.items())
        self.stdout.write("Single-key shortcuts for other commands:\n%s\n" % (result))

    legalFileName = re.compile(r'''^[^"'\s]+$''')
    def parseRedirector(self, statement, symbol, mustBeTerminated=False):
        parts = statement.split(symbol)
        if (len(parts) < 2):
            return statement, None
        if mustBeTerminated and (not self.statementEndPattern.search(parts[-2])):            
            return statement, None
        (newStatement, redirect) = (symbol.join(parts[:-1]), parts[-1].strip())
        if redirect:
            if not self.legalFileName.search(redirect):
                return statement, None
        else:
            redirect = self._TO_PASTE_BUFFER
        return newStatement, redirect
    
    def extractCommand(self, statement):
        try:
            (command, args) = statement.split(None,1)
        except ValueError:
            (command, args) = statement, ''
        if self.caseInsensitive:
            command = command.lower()
        return command, args
    
    def parseRedirectors(self, statement):
        mustBeTerminated = self.extractCommand(statement)[0] in self.multilineCommands
        newStatement, redirect = self.parseRedirector(statement, '>>', mustBeTerminated)
        if redirect:            
            return newStatement, redirect, 'a'        
        newStatement, redirect = self.parseRedirector(statement, '>', mustBeTerminated)
        if redirect:
            return newStatement, redirect, 'w'
        newStatement, redirect = self.parseRedirector(statement, '<', mustBeTerminated)
        if redirect:
            return newStatement, redirect, 'r'
        return statement, '', ''
           
    def onecmd(self, line):
        """Interpret the argument as though it had been typed in response
        to the prompt.

        This may be overridden, but should not normally need to be;
        see the precmd() and postcmd() methods for useful execution hooks.
        The return value is a flag indicating whether interpretation of
        commands by the interpreter should stop.

        """
        command, args = self.extractCommand(line)
        statement = ' '.join([command, args])
        if command in self.multilineCommands:
            statement = self.finishStatement(statement)
        statekeeper = None
        stop = 0
        statement, redirect, mode = self.parseRedirectors(statement)
        if redirect == self._TO_PASTE_BUFFER:
            try:
                clipcontents = getPasteBuffer()
                if mode in ('w', 'a'):
                    statekeeper = Statekeeper(self, ('stdout',))
                    self.stdout = tempfile.TemporaryFile()
                    if mode == 'a':
                        self.stdout.write(clipcontents)
                else:
                    statement = '%s %s' % (statement, clipcontents)
            except OSError, e:
                print e
                return 0
        elif redirect:
            if mode in ('w','a'):
                statekeeper = Statekeeper(self, ('stdout',))
                self.stdout = open(redirect, mode)            
            else:
                statement = '%s %s' % (statement, self.fileimport(statement=statement, source=redirect))
        stop = cmd.Cmd.onecmd(self, statement)
        try:
            if command not in self.excludeFromHistory:
                self.history.append(statement)
        finally:
            if statekeeper:
                if redirect == self._TO_PASTE_BUFFER:
                    self.stdout.seek(0)
                    writeToPasteBuffer(self.stdout.read())
                self.stdout.close()
                statekeeper.restore()
            return stop        
        
    statementEndPattern = re.compile(r'[%s]\s*$' % terminators)        
    def statementHasEnded(self, lines):
        #import pdb; pdb.set_trace()
        return bool(self.statementEndPattern.search(lines)) \
               or lines[-3:] == 'EOF' \
               or self.parseRedirectors(lines)[1]
    
    def finishStatement(self, firstline):
        statement = firstline
        while not self.statementHasEnded(statement):
            inp = self.pseudo_raw_input(self.continuationPrompt)
            statement = '%s\n%s' % (statement, inp)
        return statement
        # assembling a list of lines and joining them at the end would be faster, 
        # but statementHasEnded needs a string arg; anyway, we're getting
        # user input and users are slow.
        
    def pseudo_raw_input(self, prompt):
        """copied from cmd's cmdloop; like raw_input, but accounts for changed stdin, stdout"""
        
        if self.use_rawinput:
            try:
                line = raw_input(prompt)
            except EOFError:
                line = 'EOF'
        else:
            self.stdout.write(prompt)
            self.stdout.flush()
            line = self.stdin.readline()
            if not len(line):
                line = 'EOF'
            else:
                if line[-1] == '\n': # this was always true in Cmd
                    line = line[:-1] 
        return line
                          
    def cmdloop(self, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.
        """

        # An almost perfect copy from Cmd; however, the pseudo_raw_input portion
        # has been split out so that it can be called separately
        
        self.preloop()
        if self.use_rawinput and self.completekey:
            try:
                import readline
                self.old_completer = readline.get_completer()
                readline.set_completer(self.complete)
                readline.parse_and_bind(self.completekey+": complete")
            except ImportError:
                pass
        try:
            if intro is not None:
                self.intro = intro
            if self.intro:
                self.stdout.write(str(self.intro)+"\n")
            stop = None
            while not stop:
                if self.cmdqueue:
                    line = self.cmdqueue.pop(0)
                else:
                    line = self.pseudo_raw_input(self.prompt)
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            self.postloop()
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    import readline
                    readline.set_completer(self.old_completer)
                except ImportError:
                    pass    

    def do_EOF(self, arg):
        return True
    do_eof = do_EOF
               
    def clean(self, s):
        """cleans up a string"""
        if self.caseInsensitive:
            return s.strip().lower()
        return s.strip()
    
    def parseline(self, line):
        """Parse the line into a command name and a string containing
        the arguments.  Returns a tuple containing (command, args, line).
        'command' and 'args' may be None if the line couldn't be parsed.
        """
        line = line.strip()
        if not line:
            return None, None, line
        shortcut = self.shortcuts.get(line[0])
        if shortcut and hasattr(self, 'do_%s' % shortcut):
            line = '%s %s' % (shortcut, line[1:])
        i, n = 0, len(line)
        while i < n and line[i] in self.identchars: i = i+1
        cmd, arg = line[:i], line[i:].strip().strip(self.terminators)
        return cmd, arg, line
    
    def showParam(self, param):
        param = self.clean(param)
        if param in self.settable:
            val = getattr(self, param)
            self.stdout.write('%s: %s\n' % (param, str(getattr(self, param))))

    def do_quit(self, arg):
        return 1
    do_exit = do_quit
    do_q = do_quit
    
    def do_show(self, arg):
        'Shows value of a parameter'
        if arg.strip():
            self.showParam(arg)
        else:
            for param in self.settable:
                self.showParam(param)
    
    def do_set(self, arg):
        'Sets a parameter'        
        try:
            paramName, val = arg.split(None, 1)
            paramName = self.clean(paramName)
            if paramName not in self.settable:
                raise NotSettableError                            
            currentVal = getattr(self, paramName)
            val = cast(currentVal, val.strip(self.terminators))
            setattr(self, paramName, val)
            self.stdout.write('%s - was: %s\nnow: %s\n' % (paramName, currentVal, val))
        except (ValueError, AttributeError, NotSettableError), e:
            self.do_show(arg)
                
    def do_shell(self, arg):
        'execute a command as if at the OS prompt.'
        os.system(arg)
        
    def do_history(self, arg):
        """history [arg]: lists past commands issued
        
        no arg -> list all
        arg is integer -> list one history item, by index
        arg is string -> string search
        arg is /enclosed in forward-slashes/ -> regular expression search
        """
        if arg:
            history = self.history.get(arg)
        else:
            history = self.history
        for hi in history:
            self.stdout.write(hi.pr())
    def last_matching(self, arg):
        try:
            if arg:
                return self.history.get(arg)[-1]
            else:
                return self.history[-1]
        except:
            return None        
    def do_list(self, arg):
        """list [arg]: lists last command issued
        
        no arg -> list absolute last
        arg is integer -> list one history item, by index
        - arg, arg - (integer) -> list up to or after #arg
        arg is string -> list last command matching string search
        arg is /enclosed in forward-slashes/ -> regular expression search
        """
        try:
            self.stdout.write(self.last_matching(arg).pr())
        except:
            pass
    do_hi = do_history
    do_l = do_list
    do_li = do_list
        
    def do_ed(self, arg):
        """ed: edit most recent command in text editor
        ed [N]: edit numbered command from history
        ed [filename]: edit specified file name
        
        commands are run after editor is closed.
        "set edit (program-name)" or set  EDITOR environment variable
        to control which editing program is used."""
        if not self.editor:
            print "please use 'set editor' to specify your text editing program of choice."
            return
        filename = self.defaultFileName
        buffer = ''
        try:
            arg = int(arg)
            buffer = self.last_matching(arg)
        except:
            if arg:
                filename = arg
            else:
                buffer = self.last_matching(arg)

        if buffer:
            f = open(filename, 'w')
            f.write(buffer or '')
            f.close()        
                
        os.system('%s %s' % (self.editor, filename))
        self.do_load(filename)
    do_edit = do_ed
    
    def do_save(self, fname=None):
        """Saves most recent command to a file."""
        
        if fname is None:
            fname = self.defaultFileName
        try:
            f = open(fname, 'w')
            f.write(self.history[-1])
            f.close()
        except Exception, e:
            print 'Error saving %s: %s' % (fname, str(e))
            
    def do_load(self, fname=None):
        """Runs command(s) from a file."""
        if fname is None:
            fname = self.defaultFileName        
        keepstate = Statekeeper(self, ('stdin','use_rawinput','prompt','continuationPrompt'))
        try:
            self.stdin = open(fname, 'r')
        except IOError, e:
            try:
                self.stdin = open('%s.%s' % (fname, self.defaultExtension), 'r')
            except IOError:
                print 'Problem opening file %s: \n%s' % (fname, e)
                keepstate.restore()
                return
        self.use_rawinput = False
        self.prompt = self.continuationPrompt = ''
        self.cmdloop()
        self.stdin.close()
        keepstate.restore()
        self.lastcmd = ''
        
    def do_run(self, arg):
        """run [arg]: re-runs an earlier command
        
        no arg -> run most recent command
        arg is integer -> run one history item, by index
        arg is string -> run most recent command by string search
        arg is /enclosed in forward-slashes/ -> run most recent by regex
        """        
        'run [N]: runs the SQL that was run N commands ago'
        runme = self.last_matching(arg)
        print runme
        if runme:
            runme = self.precmd(runme)
            stop = self.onecmd(runme)
            stop = self.postcmd(stop, runme)
    do_r = do_run        
            
    def fileimport(self, statement, source):
        try:
            f = open(source)
        except IOError:
            self.stdout.write("Couldn't read from file %s\n" % source)
            return ''
        data = f.read()
        f.close()
        return data
            
class HistoryItem(str):
    def __init__(self, instr):
        str.__init__(self, instr)
        self.lowercase = self.lower()
        self.idx = None
    def pr(self):
        return '-------------------------[%d]\n%s\n' % (self.idx, str(self))
        
class History(list):
    rangeFrom = re.compile(r'^([\d])+\s*\-$')
    def append(self, new):
        new = HistoryItem(new)
        list.append(self, new)
        new.idx = len(self)
    def extend(self, new):
        for n in new:
            self.append(n)
    def get(self, getme):
        try:
            getme = int(getme)
            if getme < 0:
                return self[:(-1 * getme)]
            else:
                return [self[getme-1]]
        except IndexError:
            return []
        except (ValueError, TypeError):
            getme = getme.strip()
            mtch = self.rangeFrom.search(getme)
            if mtch:
                return self[(int(mtch.group(1))-1):]
            if getme.startswith(r'/') and getme.endswith(r'/'):
                finder = re.compile(getme[1:-1], re.DOTALL | re.MULTILINE | re.IGNORECASE)
                def isin(hi):
                    return finder.search(hi)
            else:
                def isin(hi):
                    return (getme.lower() in hi.lowercase)
            return [itm for itm in self if isin(itm)]

class NotSettableError(Exception):
    pass
        
def cast(current, new):
    """Tries to force a new value into the same type as the current."""
    typ = type(current)
    if typ == bool:
        try:
            return bool(int(new))
        except ValueError, TypeError:
            pass
        try:
            new = new.lower()    
        except:
            pass
        if (new=='on') or (new[0] in ('y','t')):
            return True
        if (new=='off') or (new[0] in ('n','f')):
            return False
    else:
        try:
            return typ(new)
        except:
            pass
    print "Problem setting parameter (now %s) to %s; incorrect type?" % (current, new)
    return current
        
class Statekeeper(object):
    def __init__(self, obj, attribs):
        self.obj = obj
        self.attribs = attribs
        self.save()
    def save(self):
        for attrib in self.attribs:
            setattr(self, attrib, getattr(self.obj, attrib))
    def restore(self):
        for attrib in self.attribs:
            setattr(self.obj, attrib, getattr(self, attrib))        
