import nox


@nox.session(python=['3.7'])
def docs(session):
    session.install('sphinx',
                    'sphinx-rtd-theme',
                    '.',
                    'plugins/ext_test',
                    )
    session.chdir('docs')
    tmpdir = session.create_tmp()

    session.run('sphinx-build', '-a', '-W', '-T', '-b', 'html',
                '-d', '{}/doctrees'.format(tmpdir), '.', '{}/html'.format(tmpdir))


@nox.session(python=['3.5.2', '3.5.3', '3.5', '3.6', '3.7', '3.8', '3.9'])
@nox.parametrize('plugin', [None,
                            'ext_test',
                            'template',
                            'coverage'])
def tests(session, plugin):
    if plugin is None:
        session.install('invoke', './[test]')
        session.run('invoke', 'pytest', '--junit', '--no-pty', '--base')
        session.install('./plugins/ext_test/')
        session.run('invoke', 'pytest', '--junit', '--no-pty', '--isolated')
    elif plugin == 'coverage':
        session.install('invoke', 'codecov', 'coverage')
        session.run('codecov')
    else:
        session.install('invoke', './', 'plugins/{}[test]'.format(plugin))

        # cd into test directory to run other unit test
        session.run('invoke',
                    'plugin.{}.pytest'.format(plugin.replace('_', '-')),
                    '--junit',
                    '--no-pty',
                    '--append-cov',
                    )
