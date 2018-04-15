
def twitter_error_code(twitter_error):
    'Return the error code from a TwitterError exception.'
    return twitter_error.message[0]['code']
