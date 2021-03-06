from mainwindow import Ui_MainWindow
from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import json
import asyncio
import aiohttp
import time, datetime
import webbrowser
class BoxData():
    def __init__(self):
        self.search_key = ""
        self.auction_on = False
        self.box_only = True
        self.max_price = 0
        self.bnb_on = False
        self.eth_on = False

class QCustomTableWidgetItem (QtWidgets.QTableWidgetItem):
    def __init__ (self, value):
        super(QCustomTableWidgetItem, self).__init__(str('%s' % value))

    def __lt__ (self, other):
        if (isinstance(other, QCustomTableWidgetItem)):
            selfDataValue  = float(self.data(QtCore.Qt.EditRole))
            otherDataValue = float(other.data(QtCore.Qt.EditRole))
            return selfDataValue < otherDataValue
        else:
            return QtGui.QTableWidgetItem.__lt__(self, other)

class QDateItem(QtWidgets.QTableWidgetItem):
    def __init__ (self, value):
        super(QDateItem, self).__init__(str('%s' % value))
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_date)

    def update_date(self):
        data = int(self.data(QtCore.Qt.UserRole))
        if data > 0:
            data = data - 1
            self.setData(QtCore.Qt.UserRole, data) 
            self.setData(QtCore.Qt.EditRole, str(datetime.timedelta(seconds=data)))
            

    def __lt__ (self, other):
        if (isinstance(other, QDateItem)):
            selfDataValue  = int(self.data(QtCore.Qt.UserRole))
            otherDataValue = int(other.data(QtCore.Qt.UserRole))
            return selfDataValue < otherDataValue
        else:
            return QtGui.QTableWidgetItem.__lt__(self, other)

class Worker(QtCore.QThread):
    boxes_ready = QtCore.pyqtSignal(object)
    def __init__(self):
        super(Worker,self).__init__()
        self.bnbbusd = 0
        self.ethbusd = 0

        self.price_api = "https://api.binance.com/api/v3/avgPrice?symbol={0}"
        self.nft_api = "https://www.binance.com/bapi/nft/v1/public/nft/product-list"
        self.box_request_body = {
            "category" : 0, #Mystery Box
            "keyword" : 0, #Search Key
            "orderBy" : "amount_sort", 
            "orderType" : 1, #Low-high
            "page" : 1,
            "rows" : 100
        }
        self.box_to_search = None
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self.loop = asyncio.new_event_loop()

    def set_search_box(self, box):
        self.box_to_search = box

    def run(self):
        self.loop.run_until_complete(self.search_box())

    def binance_uri_generator(self,id):
        return "https://www.binance.com/en/nft/goods/blindBox/detail?productId={0}&isOpen=false&isProduct=1".format(id)

    async def search_box(self):
        if self.box_to_search is None:
            print("Kutu se??ilmedi")
            return
        async with aiohttp.ClientSession() as session:
            #Get BNB,ETH Price
            if self.box_to_search.bnb_on:
                print("Getting bnb price")
                async with session.get(self.price_api.format("BNBBUSD")) as resp:
                    data = await resp.json()
                    self.bnbbusd = float(data["price"])
            if self.box_to_search.eth_on:
                print("Gettin eth price")
                async with session.get(self.price_api.format("ETHBUSD")) as resp:
                    data = await resp.json()
                    self.ethbusd = float(data["price"])
        
            #Iterate through whole market until finished
            page_start = 1
            self.box_request_body["keyword"] = self.box_to_search.search_key
            item_list = []
            while True:
                try:
                    self.box_request_body["page"] = page_start
                    print("Iteration, ", page_start)
                    price_reached = False
                    headers = {"Clienttype":"web",
                                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"}
                    async with session.post(self.nft_api,json=self.box_request_body) as resp:
                        data = await resp.json()

                        if "total" not in data["data"] or data["data"]["total"] == 0:
                            break
                        data = data["data"]["rows"]
                        current_timestamp = time.time()
                        for box_json in data:
                            #Check if we only search boxes.Mystery boxes have nftType = 2
                            if self.box_to_search.box_only and box_json["nftType"] != 2:
                                continue
                            
                            #Check if we search auction items too. Auction items have tradeType=1
                            if not self.box_to_search.auction_on and box_json["tradeType"] == 1:
                                continue
                            
                            amount = float(box_json["amount"])
                            if box_json["currency"] == "BUSD" and amount <= self.box_to_search.max_price:
                                price = amount
                                coin = "BUSD"
                                link = self.binance_uri_generator(box_json["productId"])
                                end_time = box_json["setEndTime"] / 1000
                                end_timestamp = int(end_time - current_timestamp) if self.box_to_search.auction_on else 0
                                item_list.append((price,coin,end_timestamp,link))
                            #Check if bnb on
                            elif box_json["currency"] == "BNB" and self.box_to_search.bnb_on and amount * self.bnbbusd <= self.box_to_search.max_price:
                                price = amount * self.bnbbusd
                                coin = "BNB"
                                link = self.binance_uri_generator(box_json["productId"])
                                end_time = box_json["setEndTime"] / 1000
                                end_timestamp = int(end_time - current_timestamp) if self.box_to_search.auction_on else 0
                                item_list.append((price,coin,end_timestamp,link))
                            #Check if eth on
                            elif box_json["currency"] == "ETH" and self.box_to_search.eth_on and amount * self.ethbusd <= self.box_to_search.max_price:
                                price = amount * self.ethbusd
                                coin = "ETH"
                                link = self.binance_uri_generator(box_json["productId"])
                                end_time = box_json["setEndTime"] / 1000
                                end_timestamp = int(end_time - current_timestamp) if self.box_to_search.auction_on else 0
                                item_list.append((price,coin,end_timestamp,link))
                            
                            if box_json["currency"] == "BUSD" and amount > self.box_to_search.max_price:
                                price_reached = True

                            #Pass to table
                            if len(item_list) >= 10:
                                self.boxes_ready.emit(set(item_list))
                                item_list.clear()
                        
                        #Pass to table
                        if len(item_list) > 0:
                            self.boxes_ready.emit(set(item_list))
                            item_list.clear()

                    if price_reached:
                        break
                    page_start += 1
                    time.sleep(0.05)
                except Exception as e:
                    print("Exception:",e)
                    break
            
            #print("List: ",item_list)

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super(MainWindow,self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Binance NFT Market Mystery Box Fiyat Bulma")
        self.setWindowIcon(QtGui.QIcon("block.ico"))
        self.initialize_ui()
        self.worker = Worker()
        self.worker.boxes_ready.connect(self.process_list)
        self.worker.finished.connect(self.on_worker_done)

    def initialize_ui(self):
        self.ui.cb_special.stateChanged.connect(self.ui.le_special.setEnabled)
        self.ui.cb_special.stateChanged.connect(self.ui.cb_box_list.setDisabled)
        self.ui.tableWidget.itemDoubleClicked.connect(self.open_link)
        with open ("search.json","r") as file:
            self.json_data = json.load(file)
        self.ui.cb_box_list.insertItems(0, self.json_data.keys())

    def open_link(self,item):
        if item.column() == 3:
            webbrowser.open(item.text())

    @QtCore.pyqtSlot(bool)
    def on_pb_search_clicked(self,checked):
        box_data = BoxData()
        box_data.max_price = self.ui.dsb_price.value()
        box_data.auction_on = self.ui.cb_auction.isChecked()
        box_data.bnb_on = self.ui.cb_bnb.isChecked()
        box_data.eth_on = self.ui.cb_eth.isChecked()
        box_data.box_only = self.ui.cb_box_only.isChecked()
        box_data.search_key = self.json_data[self.ui.cb_box_list.currentText()] if not self.ui.cb_special.isChecked() else self.ui.le_special.text()

        #print("Search: " , box_data.search_key ," Price:",box_data.max_price," Auction:",box_data.auction_on, " BNB on: ", box_data.bnb_on , " ETH on: ", box_data.eth_on, " Box only: " , box_data.box_only)
        #Clean Up
        self.ui.tableWidget.setRowCount(0)
        self.ui.tableWidget.setSortingEnabled(False)
        self.ui.pb_search.setText("Arama yap??l??yor. Bekleyiniz...")
        self.ui.pb_search.setEnabled(False)
        self.worker.set_search_box(box_data)
        self.worker.start()

    def process_list(self,items):
        for item in items:
            price = item[0]
            symbol = item[1]
            time = item[2]
            link = item[3]

            self.ui.tableWidget.insertRow(0)
            self.ui.tableWidget.setItem(0, 0, QCustomTableWidgetItem(price))
            self.ui.tableWidget.setItem(0, 1, QtWidgets.QTableWidgetItem(symbol))
            dateitem = QDateItem(str(datetime.timedelta(seconds=time)))
            dateitem.setData(QtCore.Qt.UserRole, time)
            self.ui.tableWidget.setItem(0, 2, dateitem)
            self.ui.tableWidget.setItem(0, 3, QtWidgets.QTableWidgetItem(link))

            if self.ui.db_oto.value() >= price:
                webbrowser.open(link)

    def on_worker_done(self):
        self.ui.tableWidget.setSortingEnabled(True)
        self.ui.pb_search.setText("Arama Yap")
        self.ui.pb_search.setEnabled(True)
        if self.ui.cb_auction.isChecked():
            for i in range(self.ui.tableWidget.rowCount()):
                self.ui.tableWidget.item(i, 2).timer.start(1000)

    @QtCore.pyqtSlot(bool)
    def on_actionAbout_triggered(self,check):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Mystery Box Kutu Bulma")
        verticalL = QtWidgets.QVBoxLayout(dialog)
       
        codedLb = QtWidgets.QLabel(dialog)
        codedLb.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        codedLb.setText("??cretsiz olarak yay??nlad??????m Binance NFT marketinde istedi??iniz \nMysteryBox bulma program??. Ufakta olsa i??inize yarar umar??m.\nBa?????? yapmak isteyenler i??in USDT TRC20 c??zdan??: \nTAXZUus2E5zWDuKph3pk7Tk3ajEhLRpaMa\nBEP20 c??zdan??:\n0x196eE6eE93602907b3Be2E26c215838EA2d3cD35\nCoded By GALL3X")

        verticalL.addWidget(codedLb)

        dialog.setLayout(verticalL)
        dialog.resize(400,150)
        dialog.setFixedSize(dialog.width(),dialog.height())
        dialog.show()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()

    app.exec_()