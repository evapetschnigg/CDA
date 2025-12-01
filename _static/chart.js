let marketTime = js_vars.marketTime
let framing = js_vars.framing || ''

function redrawChart(series) {
        // Determine asset/carbon credit text based on framing
        let assetType = (framing === 'environmental' || framing === 'destruction') ? 'carbon credits' : 'assets'
        
        Highcharts.chart('highchart', {

            title: {
                text: 'Trade history'
            },
            subtitle: {
                text: 'Prices at which group members traded ' + assetType + ' this round',
                style: {
                    fontSize: '0.9em'
                }
            },
            yAxis: {
                title: {
                    text: 'Price'
                }
            },
            xAxis: {
                title: {
                    text: 'Time (seconds)'
                },
                min: 0,
                max: marketTime ,
            },
            legend: {
                enabled: true
            },

            plotOptions: {
                series: {
                    label: {
                        enabled: true
                    },
                }
            },

            series: series,

            credits: {
                enabled: false
            }
        });
    }