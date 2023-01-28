import nox


@nox.session(python=['3.7', '3.8', '3.9', '3.10', '3.11'])
def tests(session):
    session.install('invoke', './[test]')
    session.run('invoke', 'pytest', '--junit', '--no-pty')
