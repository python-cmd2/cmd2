import nox


@nox.session(python=['3.7'])
def docs(session):
    session.install('sphinx', 'sphinx-rtd-theme', '.')
    session.chdir('docs')
    tmpdir = session.create_tmp()

    session.run('sphinx-build', '-a', '-W', '-T', '-b', 'html',
                '-d', '{}/doctrees'.format(tmpdir), '.', '{}/html'.format(tmpdir))


@nox.session(python=['3.5', '3.6', '3.7', '3.8', '3.9'])
def tests(session):
    session.install('invoke', './[test]')
    session.run('invoke', 'pytest', '--junit', '--no-pty')

    # cd into test directory to run other unit test
    session.chdir('./plugins/ext_test')
    session.install('.[test]')
    session.run('invoke', 'pytest', '--junit', '--no-pty', '--append-cov')

    # return to top directory to submit coverage
    session.chdir('../..')
    session.run('codecov')
