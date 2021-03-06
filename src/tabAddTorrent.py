import json
import time

import requests
import requests.exceptions
from PyQt5.QtCore import pyqtSlot

from misc import readRPCfile, highlight_textbox, printException, getCallerName, getFunctionName
from qt.gui_tabAddTorrent import TabAddTorrent_gui
from threads import ThreadFuns


class TabAddTorrent(object):
    UPDATE_HALF_PERIOD = 5
    BLOCK_DELAY = 6
    def __init__(self, caller):
        self.caller = caller

        self.ui = TabAddTorrent_gui(caller)
        self.caller.tabAddTorrent = self.ui

        self.ui.submitBtn.clicked.connect(lambda: self.submitTorrent())

        rpc_ip, rpc_port, rpc_user, rpc_passwd = readRPCfile()
        self.server_uri = 'http://{}:{}'.format(rpc_ip, rpc_port)
        self.auth_pair = rpc_user, rpc_passwd

        self.current_block = None
        self.next_super = None
        self.update = False
        ThreadFuns.runInThread(self.updater, ())

    @staticmethod
    def prepare_budget_json(name, uri, payee, cat, super_block):
        return json.dumps({
            'jsonrpc': 1.0,
            'id': 'curltest',
            'method': 'preparebudget',
            'params': ["[" + cat + "] " + name,
                       uri,
                       1,
                       super_block,
                       payee,
                       5]
        })

    @staticmethod
    def submit_budget_json(name, uri, payee, cat, super_block, hash):
        return json.dumps({
            'jsonrpc': 1.0,
            'id': 'curltest',
            'method': 'submitbudget',
            'params': ["[" + cat + "] " + name,
                       uri,
                       1,
                       super_block,
                       payee,
                       5,
                       hash]
        })

    def updater(self, ctrl):
        while True:
            time.sleep(self.UPDATE_HALF_PERIOD)
            self.current_block = self.caller.rpcClient.getBlockCount()
            self.next_super = self.caller.rpcClient.getNextSuperBlock()
            self.update = not self.update

    def submit_torrent_thread(self, ctrl, name, uri, payee, cat):
        while not self.update:
            time.sleep(self.UPDATE_HALF_PERIOD)

        with requests.Session() as s:
            initial_block = self.current_block

            response = None
            try:
                response = s.post(self.server_uri,
                                  auth=self.auth_pair,
                                  data=self.prepare_budget_json(name,
                                                                uri,
                                                                payee,
                                                                cat,
                                                                self.next_super),
                                  headers={
                                      'Content-Type': 'text/plain'
                                  }).content.decode('ascii')
            except Exception as e:
                printException(getCallerName(),
                               getFunctionName(),
                               'Preparing the torrent failed',
                               e.args + (name, uri, payee, cat))

            response_object = json.loads(response)

            while self.current_block < initial_block + self.BLOCK_DELAY:
                time.sleep(self.UPDATE_HALF_PERIOD)

            try:
                s.post(self.server_uri,
                       auth=self.auth_pair,
                       data=self.submit_budget_json(name,
                                                    uri,
                                                    payee,
                                                    cat,
                                                    self.next_super,
                                                    response_object['result']),
                       headers={
                           'Content-Type': 'text/plain'
                       })
            except Exception as e:
                printException(getCallerName(),
                               getFunctionName(),
                               'Submitting the torrent failed',
                               e.args + (name, uri, payee, cat))

    @pyqtSlot()
    def submitTorrent(self):
        name = self.ui.fileNameTextBox.text()
        if not name:
            highlight_textbox(self.ui.fileNameTextBox, self.ui.fileNameLabel)

        payee = self.ui.paymentTextBox.text()
        if not payee:
            highlight_textbox(self.ui.paymentTextBox, self.ui.paymentLabel)

        uri = self.ui.magnetUriTextBox.text()
        if not uri:
            highlight_textbox(self.ui.magnetUriTextBox, self.ui.magnetUriLabel)

        cat = self.ui.categorySelect.currentText()

        if not all((name, uri, payee)):
            return

        ThreadFuns.runInThread(self.submit_torrent_thread,
                               (name, uri, payee, cat))
