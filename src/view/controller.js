(function () {
    var app = angular.module('AKEPView', ['angularBootstrapNavTree', 'ngAnimate']);
    app.config(function ($sceProvider) {
        $sceProvider.enabled(false);
    });
    app.controller('AKEPViewController', function ($scope, $http) {
        var converter = new showdown.Converter({'tables': true});
        $scope.CSVDelimiter = '-#-';
        $scope.delimiter = ',';

        $scope.AKEPData = [];
        $scope.AKEPController = {};
        $scope.solvediMSc = 0;
        $scope.iMScBaseSum = 0;

        $scope.listDateOptions = {
            weekday: "long", year: "numeric", month: "short",
            day: "numeric", hour: "2-digit", minute: "2-digit"
        };

        $scope.AKEP_handler = function (branch) {
            $scope.actBranch = branch;
        };
        $(window).on('hashchange', function () {
            $scope.loadContent();
        });

        $scope.createListDate = function (timestamp) {
            if (timestamp.length > 13) {
                timestamp = timestamp.substring(0, 13);
            }
            return (new Date(parseInt(timestamp + (new Array(13 - timestamp.length + 1)).join('0')))).toLocaleDateString("hu", $scope.listDateOptions);
        };

        $scope.loadContent = function () {
            $scope.error = false;
            $scope.doing_async = true;
            var url = window.location.hash.replace('#AKEPView/', '');
            if (url === '' || url[0] === '#') {
                $scope.error = true;
                $scope.errorContent = "Határozza meg a kért tartalmat!";
                return;
            }

            var akepResult = url.split('/');
            var previousResults = "";
            if (akepResult[0] === 'test') {
                url = configGlobal.testDownload + akepResult[1]
            } else {
                url = configGlobal.normalDownload + (akepResult.length === 3 ? akepResult[1] + '/' + akepResult[2] + '/' + akepResult[0] : akepResult.join('/'));
                previousResults = akepResult.length === 3 ? akepResult[1] + '/' + akepResult[2] : akepResult.join('/');
            }
            $http({'method': 'get', 'url': url})
                .then(function successCallback(response) {
                    try {
                        if (response.data.indexOf($scope.CSVDelimiter) !== -1) {
                            $scope.delimiter = $scope.CSVDelimiter;
                        }
                        var root = $($.parseXML(response.data)).find('exercise');
                    } catch (err) {
                        $scope.error = true;
                        $scope.errorContent = "Nem megfelelő XML jött vissza a szervertől!";
                        return;
                    }
                    $scope.AKEPData = [$scope.createAKEPData(root)];

                    if (previousResults) {
                        $http({
                            'method': 'get',
                            'url': configGlobal.allPreviousTests + previousResults,
                            'headers': {'Content-Type': 'application/json'}
                        }).then(function successCallback(response) {
                            var previousResultsView = ['\n\n**Korábbi értékelések ehhez a hallgatóhoz:**'];
                            response.data.forEach(function (prevResult) {
                                var resultLink = '#AKEPView/';
                                var resultText = '';
                                if (akepResult[0] === prevResult) {
                                    resultLink += akepResult[1] + '/' + akepResult[2];
                                    resultText = 'Legfrissebb';
                                } else {
                                    resultLink += prevResult + '/' + (akepResult.length === 3 ? akepResult[1] + '/' + akepResult[2] : akepResult.join('/'));
                                    resultText = prevResult.replace(/-/g, '.').replace(/_/g, ':');
                                }
                                previousResultsView.push('<a href="' + resultLink + '">' + resultText + '</a>');
                            });
                            if (previousResultsView.length > 1) {
                                $scope.rootAKEPData.infoArray = $scope.rootAKEPData.infoArray.concat(previousResultsView.join('\n- '));
                                $scope.rootAKEPData.info = converter.makeHtml(
                                    $scope.rootAKEPData.infoArray.join('\n')
                                );
                            }
                        });
                    }

                    var maxBaseScore = $scope.rootAKEPData.score ? Number($scope.rootAKEPData.score.split('/')[1]) : 0;
                    var solvedScore = $scope.rootAKEPData.score ? Number($scope.rootAKEPData.score.split('/')[0]) : 0;
                    var scoreMinToiMSc = Math.round(maxBaseScore * 0.85);
                    var iMScText = '**iMSc pont:** `';
                    if ($scope.solvediMSc > 0 && solvedScore - $scope.solvediMSc >= scoreMinToiMSc) {
                        iMScText += Math.min(10, Math.round(solvedScore / maxBaseScore * 100) - 85) + ' pont`\n\nCsak abban az esetben helyes a fenti érték, ha a tesztek minden feladatra el lettek készítve és helyes az AKÉP pontozás.\n\nJogosult az iMSc pontra, mert\n- Megoldott iMSc feladat: `' + $scope.solvediMSc + ' pont`\n- Minimum szükséges pontszám: `' + scoreMinToiMSc + ' pont`';
                    } else {
                        iMScText += '0 pont`, mert ' + ($scope.solvediMSc === 0 ? 'nem szerzett pontot (i)-vel jelölt feladatra.' : 'nem érte el az (i) jelű pontszámok nélkül a minimális ' + scoreMinToiMSc + ' pontot.');
                    }
                    $scope.rootAKEPData.infoArray = $scope.rootAKEPData.infoArray.concat(iMScText);
                    $scope.rootAKEPData.info = converter.makeHtml(
                        $scope.rootAKEPData.infoArray.join('\n')
                    );
                    $scope.doing_async = false;
                    $scope.AKEPController.select_branch($scope.AKEPData[0]);
                    $scope.AKEPController.expand_branch();
                }, function errorCallback(response) {
                    $scope.error = true;
                    switch (response.status) {
                        case 401:
                            $scope.errorContent = converter.makeHtml("A kért tartalomhoz nincs jogosultsága!\n\nLépjen be majd frissítsen!\n\n[" + configGlobal.unauthorizedTOUrl + "](" + configGlobal.unauthorizedTOUrl + ")");
                            break;
                        case 404:
                            $scope.errorContent = "A kért tartalom nem elérhető!";
                            break;
                        default:
                            $scope.errorContent = response.data;
                    }
                });
        };
        $scope.createLabel = function (element) {
            var prior = ['exerciseID', 'title', 'evaluateMode', 'n'];
            var selected = prior.find(function (e) {
                return element.attr(e) !== undefined;
            });
            if (selected === undefined) {
                return $scope.createLabel(element.parent()) + '.' + element.attr('operator');
            }
            return element.attr(selected);
        };
        $scope.createResultColor = function (min, max) {
            var nmin = Number(min);
            var nmax = Number(max);
            var result = nmin / nmax * 100;
            var hue = Math.floor(result * 120 / 100);
            var saturation = Math.floor(Math.abs(result - 50) / 50 * 100);
            return 'hsl(' + hue + ',' + saturation + '%,40%)';
        };
        $scope.formalRequiremensType = function (reqType) {
            var types = {
                'containAnd': 'Tartalmazza az összeset',
                'regexpToInput': 'Passzoljon a reguláris kifejezéshez',
                'containOr': 'Tartalmazza legalább az egyiket',
                'ColumnsEqualParam': 'Tartalmazza mindegyik oszlopot',
                'rowNumEq': 'A sorok száma legyen ennyi',
                'rowNumGrEq': 'A sorok száma legyen ennyi vagy több',
                'rowNumLtEq': 'A sorok száma legyen ennyi vagy kevesebb',
                'cellData': 'A táblázat passzoljon a következőhöz'
            };
            return types[reqType];
        };
        $scope.outputShowChange = function (actBranch) {
            actBranch.fullOutputShow = !actBranch.fullOutputShow;
            actBranch.buttonText = !actBranch.fullOutputShow ? 'Teljes kimenet' : 'Releváns kimenet';
        };
        $scope.getSeparator = function (reqType) {
            if (reqType.indexOf('contain') > -1) return ';';
            if (reqType === 'cellData') return '|||';
            if (reqType === 'ColumnsEqualParam') return $scope.delimiter;
            return false;
        };
        $scope.cellDataType = function (cellData) {
            var wholeRowType = cellData.indexOf('::') > 0;
            var cell = cellData.split(wholeRowType ? '::' : ':');
            var position = cell[0].split(',');
            var prefix = '';
            if (wholeRowType && position[0] === '*') prefix = 'Legalább egy sor';
            else if (wholeRowType) prefix = 'A ' + (Number(position[0]) + 1) + '. sor';
            else if (position[0] === '*' && position[1] === '*') prefix = 'Legalább egy sor egy oszlopában lévő cella';
            else if (position[1] === '*') prefix = 'A ' + (Number(position[0]) + 1) + '. sor legalább egy cellája';
            else if (position[0] === '*') prefix = 'Legalább egy sor ' + (Number(position[1]) + 2) + '. oszlopa';
            else prefix = 'A ' + (Number(position[0]) + 1) + '. sor ' + (Number(position[1]) + 2) + '. oszlopa';
            return prefix + ' illeszkedjen a következőhöz: ' + cell[1];

        };
        $scope.createRequiredOutput = function (actReq, successReq, cellData) {
            var result = [];
            actReq.forEach(function (val, index) {
                result.push({
                    'requirement': cellData ? $scope.cellDataType(val) : val,
                    'success': successReq[index]
                });
            });
            return result;
        };

        $scope.createExpression = function (root) {
            var operator = root.attr('operator') ? root.attr('operator') : 'or';
            var operands = [];
            var negation = root.attr('negation') !== undefined ? '!' : '';
            root.children('solution').each(function () {
                operands.push(negation + $scope.createExpression($(this)));
            });
            return operands.length == 0 ? negation + $scope.createLabel(root) : '(' + operands.join(' ' + operator + ' ') + ')';
        };

        $scope.createBonusMinusText = function (scoreArray) {
            result = [];
            scoreArray.forEach(function (score) {
                var preTag = score.value === 'fail'
                    ? 'Elégtelen osztályzat'
                    : ((score.scoreType === 'minus' ? '- ' : '+ ') + score.value + ' '
                       + (score.metricType === 'percentage' ? '%' : ( score.metricType === 'grade' ? 'jegy' : 'pont')));
                result.push('- `' + preTag + '` az ' + (score.extension === 'full' ? 'egész mérésre' : 'aktuális feladatra') + ', ha ' + score.description.charAt(0).toLowerCase() + score.description.slice(1) + '\n');
            });
            return result;
        };

        $scope.showStream = function (stream, title) {
            var toConvert = title + '\n\t';
            if ($(stream).children().length !== 0) {
                toConvert += $(stream).html().replace(/\t/g, '').trim().replace(/\n/g, '\n\t');
            } else {
                toConvert += $(stream).text().replace(/\t/g, '').trim().replace(/\n/g, '\n\t');
            }
            return converter.makeHtml(toConvert);
        };

        $scope.parseCSV = function (text, delimiter) {
            var rows = text.replace(/"/g, '').trim().split('\n');
            var result = {
                header: null,
                content: []
            };
            var parseErrorException = {};
            if (rows.length > 1) {
                result.header = rows[0].split(delimiter);
                rows.splice(0, 1);
                try {
                    rows.forEach(function (row) {
                        var rRow = row.split(delimiter);
                        if (rRow.length !== result.header.length) {
                            throw parseErrorException;
                        }
                        result.content.push(rRow);
                    });
                    return result;
                } catch (e) {
                    if (e !== parseErrorException) throw e;
                }
            }
            return null;
        };

        $scope.showDependencies = function (dependencies, root) {
            var result = [];
            dependencies.each(function () {
                var dependency = $(this);
                var referenceAttr = dependency.attr('n') ? 'n' : 'id';
                var targetName = '';
                if (dependency.attr('error') !== 'reference'){
                    var target = root.parents('exercise').find('[' + referenceAttr + '="' + (referenceAttr === 'id' ? dependency.attr('reference-id') : dependency.attr(referenceAttr)) + '"]');
                    while (target.prop('tagName') !== 'exercise') {
                        targetName = $scope.createLabel(target) + (targetName ? '/' + targetName : '');
                        target = target.parent();
                    }
                }
                result.push({
                    reference: targetName ? targetName : 'A hivatkozott elem nem található',
                    success: !dependency.attr('error'),
                    failedText: dependency.attr('error') === 'reference' ? 'Hivatkozási hiba' : 'Az elem pontszáma kevés',
                    minScore: dependency.attr('minScore')
                })
            });
            return result;
        };

        $scope.createAKEPData = function (root, outputs) {
            var newChild = {};
            newChild.buttonText = 'Teljes kimenet';
            newChild.label = $scope.createLabel(root);

            newChild.negation = root.attr('negation') !== undefined;

            newChild.scoreType = root.attr('type');

            if (root.children('output').length !== 0) {
                var mustOutputs = [];
                root.children('output').each(function () {
                    var data = $scope.parseCSV($(this).text(), $scope.delimiter);
                    if (data === null) {
                        data = {
                            header: [],
                            content: $scope.showStream(this, '')
                        };
                    }
                    data.title = 'Kimenet a ' + $(this).attr('channelName') + ' csatornán '+($(this).attr('errorCheck') === '' ? '(standard error stream-jén)' : '')+':';
                    mustOutputs.push(data);
                });
                newChild.outputs = mustOutputs;
            }

            newChild.dependencies = $scope.showDependencies(root.children('dependency'), root);

            if (root.attr('error') !== undefined) {
                var errorText = "###Hiba\n";
                switch (root.attr('error')) {
                    case 'channelError':
                        errorText += "A hallgató nem oldotta meg a feladatot.";
                        break;
                    default:
                        errorText += 'A hallgatói munka AKÉP ellenőrzésekor hiba történt.\n\nA hibákat a megfelelő személyek vizsgálják, és az aktuális mérésgurut informálják róla.\n\nEz lehet hosszabb folyamat is.\n\n**Minimális információ a hiba okáról**\n\n\t' + root.attr('error');
                        break;
                }
                newChild.error = converter.makeHtml(errorText);
            }

            if (root.prop('tagName') === 'exercise' || root.prop('tagName') === 'task' || root.prop('tagName') == 'solution' && root.attr('evaluateMode') === undefined) {
                newChild.info = ['###Információk'];
                if (root.attr('exerciseID') !== undefined) {
                    $scope.sancBon = {
                        general: [],
                        all: []
                    };
                    root.children('extra-scoring').children('score').each(function () {
                        var score = $(this);
                        var scoreObj = {
                            scoreType: score.attr('scoreType'),
                            value: score.attr('value'),
                            metricType: score.attr('metricType'),
                            extension: score.attr('extension')
                        };
                        scoreObj.description = score.children('description').text();
                        if (score.children('apply-to').length === 0) {
                            $scope.sancBon.general.push(scoreObj);
                        } else {
                            score.children('apply-to').each(function () {
                                taskTo = $(this);
                                if (taskTo.attr('n') === 'all') {
                                    $scope.sancBon.all.push(scoreObj);
                                } else {
                                    if (!(taskTo.attr('n') in $scope.sancBon)) {
                                        $scope.sancBon[taskTo.attr('n')] = [scoreObj];
                                    } else {
                                        $scope.sancBon[taskTo.attr('n')].push(scoreObj);
                                    }
                                }
                            });
                        }
                    });
                    if (root.attr('timeStamp')) {
                        newChild.info.push('**Értékelés időpontja:** `' + $scope.createListDate(root.attr('timeStamp')) + '`\n');
                    }
                    newChild.info.push('**Hallgató azonosító:** `' + root.attr('ownerID') + '`\n');
                    newChild.info.push('**Labor:** `' + root.attr('exerciseID').split('-')[1] + '`\n');
                    newChild.info.push('**Feladatsor:** `' + root.attr('exerciseID').split('-')[0] + '`\n');
                    if ($scope.sancBon.general.length !== 0) {
                        newChild.info.push('**Nem feladatfüggő szankciók vagy bónuszpontok:**\n');
                        newChild.info = newChild.info.concat($scope.createBonusMinusText($scope.sancBon.general));
                    }
                    $scope.rootAKEPData = newChild;
                }
                if (root.children('solution').length !== 0) {
                    newChild.info.push('**Szükséges feltétel:**\n\n\t' + $scope.createExpression(root) + '\n');
                }
                newChild.infoArray = newChild.info;

                if ($scope.sancBon.all.length !== 0 && root.attr('exerciseID') === undefined || root.attr('n') in $scope.sancBon) {
                    newChild.info.push('**Feladatfüggő szankciók vagy bónuszpontok:**\n');
                    newChild.info = newChild.info.concat($scope.createBonusMinusText($scope.sancBon.all));
                    newChild.info = newChild.info.concat($scope.createBonusMinusText(root.attr('n') && root.attr('n') in $scope.sancBon ? $scope.sancBon[root.attr('n')] : []));
                }

                newChild.info = converter.makeHtml(newChild.info.join('\n'));
            }

            if (root.attr('operator')) {
                newChild.operator = root.attr('operator');
            } else if (root.children('solution').length != 0) {
                newChild.operator = 'or';
            }

            if (root.attr('resultScore') !== undefined && (root.attr('maxScore') !== undefined || root.attr('score') !== undefined)) {
                var max = root.attr('maxScore') !== undefined ? root.attr('maxScore') : root.attr('score');
                var min = root.attr('resultScore');
                if (root.attr('imscNormal')) {
                    $scope.solvediMSc += Math.min(Number(root.attr('imscNormal')), Number(min));
                    $scope.iMScBaseSum += Number(root.attr('imscNormal'));
                }
                newChild.score = min + '/' + max;
                newChild.color = $scope.createResultColor(min, max);
            }

            if (root.children('inputstream').length !== 0) {
                newChild.input = $scope.showStream(root.children('inputstream'), "###Bemenet a " + root.children('inputstream').attr('channelName') + " csatornából");
            }

            if (root.children('tasktext').length !== 0) {
                newChild.tasktext = converter.makeHtml("###Feladat\n" + $(root.children('tasktext')).text().replace(/\t/g, ''));
            }
            if (root.children('description').length !== 0) {
                newChild.description = converter.makeHtml("###Informális elvárás\n" + $(root.children('description')).text().replace(/\t/g, '').replace(/ +/g, ' '));
            }

            if (root.attr('evaluateMode') !== undefined) {
                newChild.solution = newChild.score === undefined;
                newChild.ok = root.attr('result') === 'true';
                var actOutput = outputs.filter('[channelName="' + root.attr('channelName') + '"]'+(root.attr('errorCheck') === '' ? '[errorCheck=""]' :'[errorCheck!=""]')).text().trim().toLowerCase().split('\n');
                var separator = $scope.getSeparator(root.attr('evaluateMode'));
                var actReq = separator ? root.text().trim().toLowerCase().split(separator) : [root.text().trim().toLowerCase()];
                if (actReq[actReq.length - 1] === '') {
                    actReq.splice(actReq.length - 1, 1);
                }
                var successReq = new Array(actReq.length).fill(false);
                var relevantActOutput = ['A hallgatónak nincs a tesztet igazoló kimenete vagy nincs kimenete'];
                var result = [];
                if (root.attr('error') === 'evaluateError') {
                    relevantActOutput = ['Hibás szintaxis értesítse a feladatgurut!'];
                } else if (root.attr('evaluateMode') === 'cellData') {
                    actOutput = actOutput.join('\n').replace(/"/g, '').split('\n');
                    actReq.forEach(function (req, index) {
                        try {
                            var wholeRowType = req.indexOf('::') > 0;
                            var cell = req.split(wholeRowType ? '::' : ':');
                            var position = cell[0].split(',');
                            var output = '';
                            var rowID = 0;
                            if (wholeRowType) {
                                position[1] = '*';
                            }
                            if (position[0] !== '*' && position[1] !== '*') {
                                output = (new RegExp(cell[1].replace(/\s+/g, '\\s*'))).test(actOutput[Number(position[0]) + 1].split($scope.delimiter)[Number(position[1])]) ? actOutput[Number(position[0]) + 1] : undefined;
                                if (output) {
                                    rowID = position[0];
                                }
                            } else if (position[0] !== '*') {
                                if (wholeRowType) output = (new RegExp(cell[1].replace(/\s+/g, '\\s*'))).test(actOutput[Number(position[0]) + 1]) ? actOutput[Number(position[0]) + 1] : undefined;
                                else if (position[1] === '*') {
                                    var cellOutput = actOutput[Number(position[0]) + 1].split($scope.delimiter).find(function (col) {
                                        return (new RegExp(cell[1].replace(/\s+/g, '\\s*'))).test(col);
                                    });
                                    output = cellOutput ? actOutput[Number(position[0]) + 1] : undefined;
                                }
                                if (output) {
                                    rowID = position[0];
                                }
                            } else {
                                output = actOutput.find(function (row, id) {
                                    if (wholeRowType) {
                                        if ((new RegExp(cell[1].replace(/\s+/g, '\\s*'))).test(row)) {
                                            rowID = id;
                                            return true;
                                        }
                                        return false;
                                    }
                                    if (position[1] === '*') {
                                        var cellOutput = row.split($scope.delimiter).find(function (col) {
                                            if ((new RegExp(cell[1].replace(/\s+/g, '\\s*'))).test(col)) {
                                                rowID = id;
                                                return true;
                                            }
                                            return false;
                                        });
                                        return !!cellOutput;
                                    }
                                    if (cell[1] === '') {
                                        if (row.split($scope.delimiter)[Number(position[1])] === '') {
                                            rowID = id;
                                            return true;
                                        }
                                        return false;
                                    }
                                    if ((new RegExp(cell[1].replace(/\s+/g, '\\s*'))).test(row.split($scope.delimiter)[Number(position[1])])) {
                                        rowID = id;
                                        return true;
                                    }
                                    return false;
                                });
                            }
                            if (output) {
                                result.push([Number(rowID) + 1].concat(output.split($scope.delimiter)));
                                successReq[index] = true;
                            }
                        } catch (err) {
                            err = err.stack.split('\n');
                            if (err.length > 1) {
                                console.log(err[0] + err[1]);
                            }
                            return false;
                        }
                    });
                    var header = ['sorszám'].concat(actOutput[0].split($scope.delimiter));


                    if (result.length != 0) {
                        result.splice(0, 0, header);
                    }

                    var newActOutput = [];
                    actOutput.forEach(function (row, id) {
                        if (id != 0) {
                            newActOutput.push([id].concat(row.split($scope.delimiter)));
                        }
                    });
                    if (newActOutput.length !== 0) {
                        newActOutput.splice(0, 0, header);
                    }
                    actOutput = newActOutput;
                } else if (root.attr('evaluateMode').indexOf('rowNum') >= 0) {
                    var num = Number(actReq[0]);
                    var outputNum = actOutput.length - 1;
                    switch (root.attr('evaluateMode')) {
                        case 'rowNumEq':
                            successReq[0] = num === outputNum;
                            break;
                        case 'rowNumLtEq':
                            successReq[0] = outputNum <= num;
                            break;
                        default:
                            successReq[0] = outputNum >= num;
                    }
                    result = converter.makeHtml("**A hallgató értékeket tartalmazó sorainak száma:**\n\n" + outputNum);
                } else if (root.attr('evaluateMode') === 'regexpToInput') {
                    var reg = new RegExp(actReq[0].trim().replace(/\s+/g, '\\s*'));
                    var fullOutput = actOutput.join('\t \t');
                    if (reg.test(fullOutput)) {
                        successReq[0] = true;
                        result = fullOutput.replace(new RegExp(reg), function (str) {
                            return '<span class="regHighlight">' + str + '</span>';
                        }).replace(/\t \t/g, '<br>');
                    }
                } else {
                    var fullOutput = root.attr('evaluateMode') === 'ColumnsEqualParam' ? actOutput[0].replace(/"/g, '') : actOutput.join('\t \t');
                    result = '';
                    actReq.forEach(function (req, index) {
                        var reg = new RegExp(req.trim().replace(/\s+/g, '\\s*'));
                        if (reg.test(fullOutput)) {
                            successReq[index] = true;
                            result = (result ? result : fullOutput).replace(reg, function (str) {
                                return '<span class="regHighlight">' + str + '</span>';
                            });
                        }
                    });
                    result = result.replace(/\t \t/g, '<br>');
                }
                if (result.length !== 0) {
                    relevantActOutput = result;
                }

                newChild.reqTypeText = $scope.formalRequiremensType(root.attr('evaluateMode'));
                newChild.required = $scope.createRequiredOutput(actReq, successReq, root.attr('evaluateMode') === 'cellData');
                newChild.cellType = root.attr('evaluateMode') === 'cellData' && result.length !== 0;
                newChild.header = newChild.cellType && result.length !== 0 ? relevantActOutput[0] : null;
                if (newChild.cellType && result.length !== 0) {
                    relevantActOutput.shift();
                    newChild.output = relevantActOutput;
                } else {
                    newChild.output = '<h3>Hallgató munkájának releváns kimenete</h3>' + relevantActOutput;
                }

                newChild.fulloutput = converter.makeHtml("###Hallgató munkájának raw kimenete\n\t" + actOutput.join('\n\t'));
            }

            newChild.children = [];
            var tasks = root.children('task');
            var solutions = root.children('solution');
            tasks.each(function () {
                newChild.children.push($scope.createAKEPData($(this), undefined))
            });
            solutions.each(function () {
                newChild.children.push($scope.createAKEPData($(this), outputs ? outputs : root.children('output')))
            });
            return newChild;
        };

        $scope.loadContent();
    });


}).call();
