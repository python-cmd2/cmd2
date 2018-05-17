app.cmd_echo = True
result = app.foo('aaa', 'bbb', counter=3)
out_text = 'Fail'
if result:
    data = result.data
    if 'aaa' in data.variable and 'bbb' in data.variable and data.counter == 3:
        out_text = 'Success'

print(out_text)
