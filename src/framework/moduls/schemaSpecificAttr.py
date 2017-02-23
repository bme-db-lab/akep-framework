##########################
# Schema definition keys #
##########################
# to reference system
REFERENCE_EXERCISE = 'reference'
REFERENCE_ID = 'reference-id'
REFERENCE_TARGET_ID = 'id'
REF_CHILDREN_FIND = 'refChildrenFind'
# to channel system
CH_CHAIN_CONT_COND_TYPE = ['stdout','stderr']
NO_CONTINUE_AFTER_ERROR = 'noConAfterError'
CH_INPUTSTREAM = 'inputstream'
CH_INPUT_TYPE = 'inputType'
CH_INPUTTO = 'inputTo'
CH_PATH = 'path'
CH_EXT_PATH = 'inputPath'
CH_CHAIN_CONT_COND = 'continueCondStream'
CH_ENTRY_ORDER = ['pre','con','main','post']
CH_OUT_TOTASK = 'output'
CH_OUT_TASK_TYPE = 'taskOutput'
FROM_CAHNNEL = 'fromChannel'
SCRIPT_INPUT_TYPE = ['inline','external','channelOutput']
CHANNEL_NAME_ATTR = 'name'
# to evaluate system
SCORE_TYPE = ['bonus','minus']
SOLUTION_CH_NAME = 'channelName'
EVULATION_MODE_ATTR = 'evaluateMode'
SOL_SCORE_TYPE = 'scoreType'
SCORE_ATTR = 'score'
SOL_OPERATOR = 'operator'
SOL_NEGATION = 'negation'
SOL_SHOULD_ERROR = 'errorCheck'
SOL_OTHER_OPTION = 'evaluateArgs'
# general
EXERCISE = 'exercise'
TASKTAG = 'task'
ENTRY_ATTR = 'entry'
TASK_ELEMENT_ID = 'n'
TO_ELEMENT_ERROR_ATTR = 'error'
NOT_COPY_TO_RESULT_ATTR = 'resultXML'
SOLUTION_TAG = 'solution'
EXERCISE_VARIABLES = 'exerciseKeys'
NOT_COPY_TO_RESULT_ATTR = 'resultXML'
OWNER_ID = 'ownerID'
EXERCISE_ID = 'exerciseID'


#####################
# Main program keys #
#####################
LOGGER_ID = 'AKEP'
EXERCISE_FILE_FORMAT = 'exercise.*.xml'
GLOBAL_CONF_FILE = 'akep.cfg'
BINDING_REGEX = '\$([a-zA-Z0-9-\_\@]+)\$'
CH_CON_TYPE_ANSWER_TIMEOUT = 10000
SEPARATOR_COMMUNICATE_TASK_END = '[TEND]'
ANALYSE_EVAL_PROP = ['taskID','evaluateID','evaluationFunc','score','errorType']
ANALYSE_CH_PROP = ['name','start','stop','errorType']
ANALYSE_TASK_PROP = ['taskID','score','maxScore']
ANALYSE_ASSESMENT_RUN = ['exID','ownerID','FolderID','start','stop','lastState','score%','errorType']


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
RESULT_NOT_COPY = 'notCopyFromDescription'
ASYNCANSWER = 'asyncAnswer'
ASYNCANSWER_NUM = 'asyncAnswerWorkerThreadNum'
SOLTARGET = 'solTargetDir'