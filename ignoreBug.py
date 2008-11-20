import pyparsing
statementParser = pyparsing.Combine(pyparsing.Word(pyparsing.printables)('command') +
                                            pyparsing.SkipTo('|' ^ pyparsing.stringEnd)('args') 
                                           )('statement')
print statementParser.parseString('hello there /* you | fish */ box').dump()
statementParser.ignore(pyparsing.cStyleComment)
print statementParser.parseString('hello there /* you | fish */ box').dump()
                       