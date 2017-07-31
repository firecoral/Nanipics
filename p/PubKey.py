#!/usr/local/bin/python

import sys
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

def new_key(passphrase = None):
    """Generate an RSA key-pair"""

    key = RSA.generate(2048)
    pub = key.publickey()
    return { 
	'sec_key': key.exportKey('PEM', passphrase),
	'pub_key': pub.exportKey('PEM')
    }

def encrypt(pub_key, message):
    """Encrypt a message, using the given key"""

    key = RSA.importKey(pub_key)
    cipher = PKCS1_OAEP.new(key)
    ciphertext = cipher.encrypt(message)
    return ciphertext

def decrypt(sec_key, passphrase, ciphertext):
    """Decrypt the message using the given key and passphrase"""
    key = RSA.importKey(sec_key, passphrase)
    cipher = PKCS1_OAEP.new(key)
    return cipher.decrypt(ciphertext)

