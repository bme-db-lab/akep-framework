##########################
# Schema definition keys #
##########################
REFERENCE_EXERCISE = 'reference'
REFERENCE_ID = 'reference-id'
REFERENCE_TARGET_ID = 'id'
EXERCISE = 'exercise'
CHANNEL_NAME_ATTR = 'name'
NO_CONTINUE_AFTER_ERROR = 'noConAfterError'
TASKTAG = 'task'
ENTRY_ATTR = 'entry'
CH_CHAIN_CONT_COND_TYPE = ['stdout','stderr']
TASK_ELEMENT_ID = 'n'
TO_ELEMENT_ERROR_ATTR = 'error'
SCORE_TYPE = ['bonus','minus']
SOLUTION_CH_NAME = 'channelName'
EVULATION_MODE_ATTR = 'evaluateMode'
CH_OUT_TOTASK = 'output'
SOL_SCORE_TYPE = 'scoreType'
SCORE_ATTR = 'score'
FROM_CAHNNEL = 'fromChannel'
SCRIPT_INPUT_TYPE = ['inline','external','channelOutput']
NOT_COPY_TO_RESULT_ATTR = 'resultXML'
SOLUTION_TAG = 'solution'
EXERCISE_VARIABLES = 'exerciseKeys'
REF_CHILDREN_FIND = 'refChildrenFind'
NOT_COPY_TO_RESULT_ATTR = 'resultXML'
OWNER_ID = 'ownerID'
EXERCISE_ID = 'exerciseID'
CH_INPUTSTREAM = 'inputstream'
CH_INPUT_TYPE = 'inputType'
CH_INPUTTO = 'inputTo'
CH_PATH = 'path'
CH_CHAIN_CONT_COND = 'continueCondStream'
CH_ENTRY_ORDER = ['pre','con','main','post']

#####################
# Main program keys #
#####################
LOGGER_ID = 'AKEP'
EXERCISE_FILE_FORMAT = 'exercise.*.xml'
GLOBAL_CONF_FILE = 'akep.cfg'
BINDING_REGEX = '\$([a-zA-Z0-9-\_\@]+)\$'
CH_CON_TYPE_ANSWER_TIMEOUT = 10000
SEPARATOR_COMMUNICATE_TASK_END = '[TEND]'

####################################################################
# Built in keys, You have to define this keys value in key history #
# This keys are required, you can define in GLOBAL_CONF_FILE file  #
# or in local conf file or in actual exercise or in command. The   #
# priority is reverse order!                                       #
####################################################################
EXERCISE_PATH = 'exercisesPath'
HOST = 'host'
PORT = 'port'
# optional
RESULT_NOT_COPY = 'notCopyFromDescrtiption'