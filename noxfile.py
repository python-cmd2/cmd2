import nox


@nox.session(python=['3.7'])
def docs(session):
    session.install('sphinx', 'sphinx-rtd-theme', '.')
    session.chdir('docs')
    tmpdir = session.create_tmp()

    session.run('sphinx-build', '-a', '-W', '-T', '-b', 'html',
                '-d', '{}/doctrees'.format(tmpdir), '.', '{}/html'.format(tmpdir))


@nox.session(python=['3.5', '3.6', '3.7', '3.8', '3.9'])
@nox.parametrize('plugin', [None, 'ext_test', 'template'])
def tests(session, plugin):
    if plugin is None:
        session.install('invoke', './[test]')
        session.run('invoke', 'pytest', '--junit', '--no-pty')
    else:
        session.install('invoke', '.')

        # cd into test directory to run other unit test
        session.install('plugins/{}[test]'.format(plugin))
        session.run('invoke', 'plugin.{}.pytest'.format(plugin.replace('_', '-')), '--junit', '--no-pty')

    session.run('codecov')
