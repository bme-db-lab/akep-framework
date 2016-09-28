#############################################################
# ERROR MESSAGES
ERROR = {
    'NOT_FIND' : {
        'EXERCISE_TO_ID': 'Not find exercise definition to ',
        'KEY_IN_HIERAR': 'Not find key in key hierarchy: ',
        'CH_OR_CHOUT': 'Not find {} channel or it is not have out yet, channelName: {}'
    },
    'UNEXPECTED':{
        'SOCKET_CLOSE': 'Socket unexpectedly closed, details: ',
        'AKEP_STOP':'AKÉP unexpectedly stopped, details: '
    },
    'FILE':{
        'INVALID': 'Invalid sintax in: ',
        'NOT_FIND': 'Not find file: '
    },
    'SCRIPT':{
        'MISSING_PATH':'Missing path in script: ',
        'TIME_EXPIRED':'Time expired, script: ',
        'NOT_VALID_VALUE':'Not valid value in {} key from script {}'
    },
    'GENERAL':{
        'MISSING_TO_START': 'Fail load AKÉP global configuration JSON file or exercise descriptor schema. See akep.log for details.',
        'AKEP_REQUIRED_FAIL' : 'AKEP requered things are incorrect, details: ',
        'PERMISSON': 'Permission error in ',
        'NOT_SUPPORTER_SENT': 'Not supported boolean sentence: '
    }
}
##############################################################


class AKEPException(Exception):
    pass