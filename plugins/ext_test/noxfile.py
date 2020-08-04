import nox


@nox.session(python=['3.5', '3.6', '3.7', '3.8', '3.9'])
def tests(session):
    session.install('invoke', './[test]')
    session.run('invoke', 'pytest', '--junit', '--no-pty')
