from prompt_toolkit.keys import Keys

import cmd2


def test_custom_completekey_ctrl_k():
    # Test setting a custom completekey to <CTRL> + K
    # In prompt_toolkit, this is 'c-k'
    app = cmd2.Cmd(completekey='c-k')

    assert app.completekey == 'c-k'
    assert app.session.key_bindings is not None

    # Check that we have a binding for c-k (Keys.ControlK)
    found = False
    for binding in app.session.key_bindings.bindings:
        # binding.keys is a tuple of keys
        if binding.keys == (Keys.ControlK,):
            found = True
            break

    assert found, "Could not find binding for 'c-k' (Keys.ControlK) in session key bindings"
