from os import urandom

# 30 is the recommended key length
def session_key(length):
    src = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-'
    src_len = len(src)
    str = ''

    for n in range(length):
        str = str +  src[ord(urandom(1)) % src_len]

    return str

# 16 is the recommended access_id length
def new_access_id(length):
    src = '0123456789abcdefghijklmnopqrstuvwxyz'
    src_len = len(src)
    str = ''

    for n in range(length):
        str = str +  src[ord(urandom(1)) % src_len]

    return str

# We want to process user input to avoid code insertion.
# In the past we've used regex's to remove non-numbers
# from the input string, but this is simpler.
def validate_input_int(input):
    try:
        return int(input)
    except:
        return None
