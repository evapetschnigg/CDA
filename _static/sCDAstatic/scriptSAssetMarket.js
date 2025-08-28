
    let assetsHolding = js_vars.assetsHolding

    let elTradesTable = $('#tradesTable')
    let elAssetsHolding = $('#assetsHolding')

    let lastGoodsTrade = null;


    function liveRecv(data) {
        
        // sanitise
        if (data === undefined) {
            return
        }
        
        // javascript destructuring assignment
        let {bids, asks, trades, cashHolding, assetsHolding, highcharts_series, news} = data;

        elCashHolding.html(cu(cashHolding))
        elAssetsHolding.html(assetsHolding)

        // value describes the offerID and data-value the makerID
        elBidsTableBody.html(bids.map(e => `<tr id='offerID${e[2]}' value=${e[2]} data-value=${e[3]} data-custom="1"><td value=${e[1]}>${e[1]} for </td><td value=${e[0]}>${cu(e[0])}</td></tr>`).join(''))
        elAsksTableBody.html(asks.map(e => `<tr id='offerID${e[2]}' value=${e[2]} data-value=${e[3]} data-custom="0"><td value=${e[1]}>${e[1]} for </td><td value=${e[0]}>${cu(e[0])}</td></tr>`).join(''))
        elTradesTable.html(trades.map(e => `<tr><td><span class="asset-icon"></span>${trade_desc(e[3])}&nbsp;</td><td> ${ e[1] } asset${e[1] === 1 ? '' : 's'} for&nbsp;</td><td> EUR ${ cu(e[0]) } </td></tr>`).join(''))
        // Display only the newest alert in Alerts box
        if (news && news.length > 0) {
            // Show only the most recent news message (first in the array)
            let mostRecentNews = news[0];
            elNewsTable.html(`<tr><td>${mostRecentNews[0]}</td></tr>`);
        } else {
            elNewsTable.html('<tr><td>No alerts</td></tr>');
        }

        // Add goods trade to trades table if present
        if (data.goods_trade_good && data.goods_trade_qty) {
            let tradeMessage = `You bought ${data.goods_trade_qty} unit${data.goods_trade_qty === 1 ? '' : 's'} of Good ${data.goods_trade_good}`;
            let currentTrades = elTradesTable.html();
            let newTradeRow = `<tr><td><span class="goods-icon"></span>${tradeMessage}</td><td></td><td></td></tr>`;
            elTradesTable.html(newTradeRow + currentTrades);
        }

        // Select others' Bids and Asks after this update
        $('#bidsTable tbody tr, #asksTable tbody tr').addClass('btn-outline-primary')
        // Select the own Bids and Asks after this update
        $('*[ data-value=' + my_id + ']').addClass('btn-outline-danger').removeClass('btn-outline-primary')

        // Select the Bids as Asks previously selected after this update
        if (selID !== undefined){ // checks whether a row has been selected previously{
            let prevSelected = $('#offerID' + selID) // creates a list of objects with matching offerIDs (should be unique or undefined)
            if (prevSelected !== undefined && prevSelected.length != 0) {
                let makerIDSelected = prevSelected.attr('data-value')
                if (makerIDSelected != my_id) {
                    prevSelected.removeClass('btn-outline-primary')
                    prevSelected.addClass('btn-primary')
                }
                else {
                    prevSelected.removeClass('btn-outline-danger')
                    prevSelected.addClass('btn-danger')
                }
            }
        }

        // Updates width in Bids and Asks tables between columns
        updateTableWidth()
        redrawChart(highcharts_series)

        // Goods market updates
        if (data.goodA_qty !== undefined) {
            $('#goodA_qty').text(data.goodA_qty);
        }
        if (data.goodB_qty !== undefined) {
            $('#goodB_qty').text(data.goodB_qty);
        }
        if (data.goods_utility !== undefined) {
            $('#goods_utility').text(data.goods_utility);
        }
        if (data.overall_utility !== undefined) {
            $('#overall_utility').text(data.overall_utility);
        }
        if (data.cashHolding !== undefined) {
            $('#cashHolding').text(data.cashHolding);
        }
        if (data.assetsHolding !== undefined) {
            $('#assetsHolding').text(data.assetsHolding);
        }
    }

    //this part is for the goods market
    function buyGood(good) {
        // when the qty input fields are used, uncomment the following 2 lines and make qty=1 the comment
        // let qty = good === 'A' ? $('#buyA_qty').val() : $('#buyB_qty').val();
        //qty = parseInt(qty, 10);

        let qty = 1;
        
        // Store the trade info
        lastGoodsTrade = { good: good, qty: qty };
        
        // Remove the frontend validation - let the backend handle all errors
        liveSend({
            operationType: 'buy_good',
            good: good,
            quantity: qty
        });
    }
        
    $('#buyA_btn').on('click', function() { buyGood('A'); });
    $('#buyB_btn').on('click', function() { buyGood('B'); });

    // asset market: when a limit order is placed, send to server for validation
    function sendOffer(is_bid) {
        let limitPrice = (is_bid == 0) ? $('#limitAskPrice').val() : $('#limitBidPrice').val()
        let limitVolume = (is_bid == 0) ? $('#limitAskVolume').val() : $('#limitBidVolume').val()
        
        // Default to quantity 1 if volume is empty (since inputs are hidden)
        if (!limitVolume || limitVolume === '') {
            limitVolume = 1;
        }
        
        // Send to server - let backend handle all validation
        liveSend({'operationType': 'limit_order', 'isBid': is_bid, 'limitPrice': limitPrice, 'limitVolume': limitVolume})
    }


    function sendAcc(is_bid) {
        let prevSelected = $('#offerID' + selID)
        let makerIDSelected = prevSelected.attr('data-value')
        
        if (!prevSelected.length) {
            return // No selection made
        }
        
        let offerID = selID
        let transactionPrice = prevSelected.children('td').eq(1).attr('value')
        let transactionVolume = (is_bid == 0)? $('#transactionAskVolume').val() : $('#transactionBidVolume').val()
        
        // Default to quantity 1 if volume is empty (since inputs are hidden)
        if (!transactionVolume || transactionVolume === '') {
            transactionVolume = 1;
        }
        
        // Send to server - let backend handle all validation
        liveSend({'operationType': 'market_order', 'offerID': offerID, 'isBid': is_bid, 'transactionPrice': transactionPrice, 'transactionVolume': transactionVolume})
        $('#bidsTable tbody tr, #asksTable tbody tr').removeClass('btn-primary btn-outline-primary btn-danger btn-outline-danger')
    }

    function addGoodsTrade(good, qty, price) {
        let tradeMessage = `You bought ${qty} units of Good ${good}`;
        let currentTrades = elTradesTable.html();
        let newTradeRow = `<tr><td>${tradeMessage}</td><td></td><td></td></tr>`;
        elTradesTable.html(newTradeRow + currentTrades);
    }