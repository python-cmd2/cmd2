from pyparsing import *

teststr = 'please /* ignoreme: | oops */ findme: | kthx'
parser = Word(printables)('leadWord') + SkipTo('|')('statement')
print parser.parseString(teststr).statement
parser.ignore(cStyleComment)
print parser.parseString(teststr).statement
parser = Combine(parser)
print parser.parseString(teststr).statement
parser.ignore(cStyleComment)
print parser.parseString(teststr).statement
