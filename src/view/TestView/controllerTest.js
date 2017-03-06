(function () {
    var app = angular.module('AKEPView', []);
    app.config(function ($sceProvider) {
        $sceProvider.enabled(false);
    });
    app.controller('AKEPViewTestController', function ($scope, $http) {
        $scope.workTypes = ["2016", "Aktuális", "Egyedi"];
        $scope.testStarted = false;
        $scope.progressStyle = 'info';
        $scope.success = false;
        $scope.log = false;
        var converter = new showdown.Converter();
        $scope.globalLoad = true;
        var listDateOptions = {
            weekday: "long", year: "numeric", month: "short",
            day: "numeric", hour: "2-digit", minute: "2-digit"
        };

        var createListDate = function (timestamp) {
            return (new Date(parseInt(timestamp + (new Array(13 - timestamp.length + 1)).join('0')))).toLocaleDateString("hu", listDateOptions);
        };

        $scope.errorFn = function (response) {
            $scope.globalLoad = false;
            $scope.error = true;
            $scope.success = false;
            $scope.testStarted = false;
            $scope.status = "Hiba";
            $scope.progressStyle = 'danger';
            switch (response.status) {
                case 401:
                    $scope.errorContent = converter.makeHtml("A kért tartalomhoz nincs jogosultsága!\n\nLépjen be majd frissítsen!\n\n["+configGlobal.unauthorizedTOUrl+"]("+configGlobal.unauthorizedTOUrl+")");
                    break;
                case 404:
                    $scope.errorContent = "A kért tartalom nem elérhető!";
                    break;
                default:
                    $scope.errorContent = response.data ? converter.makeHtml(response.data) : converter.makeHtml(response.responseText);
            }
            $scope.$apply();
        };

        $scope.loadContent = function (successCallback, url, method, data) {
            if (!$scope.globalLoad) {
                $scope.success = false;
                $scope.testStarted = true;
                $scope.progressStyle = 'info';
            }
            $http({'method': method, 'url': url, 'data': data, 'headers': {'Content-Type': 'application/json'}})
                .then(successCallback, $scope.errorFn);
        };

        $scope.loadContent(function successCallback(response) {
            if (response.data) {
                $scope.status = 'Töltés';
                $scope.testStarted = true;
                $scope.pollTestResult(response.data);
            }
            $scope.loadContent(function successCallback(response) {
                var compare = function (a, b) {
                    if (a.timestamp > b.timestamp)
                        return -1;
                    if (a.timestamp < b.timestamp)
                        return 1;
                    return 0;
                };
                $scope.prevTests = response.data.sort(compare);
                $scope.prevTests.forEach(function (test) {
                    test.viewDate = createListDate(test.timestamp);
                });
            }, configGlobal.downloadTests, 'get');
            $scope.globalLoad = false;
        }, configGlobal.activeTest, 'get');


        $scope.startTestRequest = function () {
            var request = new XMLHttpRequest();
            $scope.status = 'Töltés';
            $scope.progressStyle = 'info';
            request.open("POST", configGlobal.startTest);
            request.onload = function () {
                if (request.status == 200) {
                    $scope.pollTestResult(request.response);
                } else $scope.errorFn(request);
            };
            var sendData = new FormData(document.querySelector("form"));
            sendData.set('workType', $scope.test.workType);
            request.send(sendData);
        };

        $scope.printLogInfo = function(timestamp){
            $scope.log = true;
            $scope.logContent = converter.makeHtml("Log: [itt](" + configGlobal.downloadTestLog + timestamp + ")\n\nÉrtékelt munka: [itt](" + configGlobal.downloadWork + timestamp + ")");
        };

        $scope.viewPrevTest = function () {
            $scope.printLogInfo($scope.selectedPrevTest.timestamp);
            if ('error' in $scope.selectedPrevTest) {
                $scope.error = true;
                $scope.success = false;
                if ($scope.selectedPrevTest.errorText == null) {
                    $scope.selectedPrevTest.errorText = '';
                }
                $scope.errorContent = converter.makeHtml("Hiba:\n\n" + $scope.selectedPrevTest.error + "\n\n\t" + $scope.selectedPrevTest.errorText.split('\n').join('\n\t'));
            } else {
                $scope.error = false;
                $scope.success = true;
                $scope.successContent = converter.makeHtml("Értékelés elkészült!\n\nMegtekintheti [itt](" + configGlobal.urlResultView + $scope.selectedPrevTest.timestamp + ")");
            }
        };

        $scope.pollTestResult = function (timestamp) {
            $scope.loadContent(function successCallback(response) {
                try {
                    var root = $($.parseXML(response.data)).find('exercise');
                } catch (err) {
                    $scope.error = true;
                    $scope.testStarted = false;
                    $scope.errorContent = "Nem megfelelő XML jött vissza a szervertől!";
                    $scope.progressStyle = 'danger';
                    $scope.status = "Hiba";
                    return;
                }
                if (root.attr('error') !== undefined) {
                    $scope.printLogInfo(timestamp);
                    $scope.error = true;
                    $scope.status = "Hiba";
                    $scope.progressStyle = 'danger';
                    $scope.errorContent = converter.makeHtml("Hiba:\n\n" + root.attr('error') + "\n\n\t" + root.text().split('\n').join('\n\t'));
                    $scope.testStarted = false;
                    $scope.prevTests.unshift({
                        timestamp: timestamp,
                        viewDate: createListDate(timestamp),
                        error: root.attr('error'),
                        errorText: root.text()
                    });
                } else if (root.attr('status') !== undefined) {
                    $scope.status = root.attr('status');
                    setTimeout(function () {
                        $scope.pollTestResult(timestamp);
                    }, 500);
                } else {
                    $scope.printLogInfo(timestamp);
                    $scope.status = "Kész";
                    $scope.progressStyle = 'success';
                    $scope.success = true;
                    $scope.testStarted = false;
                    $scope.successContent = converter.makeHtml("Értékelés elkészült!\n\nMegtekintheti [itt](" + configGlobal.urlResultView + timestamp + ")");
                    $scope.prevTests.unshift({
                        timestamp: timestamp,
                        viewDate: createListDate(timestamp)
                    });
                }
            }, configGlobal.downloadTest + timestamp, 'get');
        };

        $scope.testStart = function () {
            $scope.error = false;
            $scope.log = false;
            $scope.startTestRequest();
        }

    });
}).call();