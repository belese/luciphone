"""@package py532lib.i2c
This module contains classes and functions related to I2C communication for the PN532 NFC Chip.

@author:  DanyO <me@danyo.ca>
@license: The source code within this file is licensed under the BSD 2 Clause license.
          See LICENSE file for more information.

"""

import os
import sys
import signal
lib_path = os.path.abspath('../')
sys.path.append(lib_path)

from time import sleep
import logging
from quick2wire.i2c import I2CMaster, reading, writing
from py532lib.i2c import *
from py532lib.frame import *
from py532lib.constants import *


LOGGING_ENABLED = False
LOG_LEVEL = logging.DEBUG
DEFAULT_DELAY = 0.005

class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException()

class Pn532_i2c:
    """Pn532_i2c abstracts away the details related to
    I2C communication with the PN532.

    """
    PN532 = None
    address = None
    i2c_channel = None
    logger = None

    def __init__(self, address=PN532_I2C_SLAVE_ADDRESS, i2c_channel=RPI_DEFAULT_I2C_NEW):
        """Constructor for the Pn532_i2c class.

        Arguments:
        @param[in]  address     I2C slave address for the PN532
                                (default = PN532_FRAME_TYPE_DATA)

        @param[in]  i2c_channel I2C channel to use.
                                (default = RPI_DEFAULT_I2C_NEW)

        """
        self.logger = logging.getLogger()
        self.logger.propagate = LOGGING_ENABLED
        if self.logger.propagate:
            self.logger.setLevel("DEBUG")

        self.address = address
        self.i2c_channel = i2c_channel
        self.PN532 = I2CMaster(self.i2c_channel)
        
    def send_command_check_ack(self, frame):
        """Sends a command frame, and waits for an ACK frame.

        Arguments:
        @param[in]  frame   Pn532Frame to send.

        """
        self.send_command(frame)
        if self.read_ack():
            return True
        else:
            return False

    def read_response(self,retry=3,timeout=False):
        """Wait, then read for a response from the PN532."""
        logging.debug("readResponse...")
        response = [b'\x00\x00\x00\x00\x00\x00\x00']

        if timeout :
          old_handler = signal.signal(signal.SIGALRM, timeout_handler)
          signal.alarm(timeout)

        c_retry = 0
        
        while timeout or (not timeout and c_retry < retry):            
             try :
                logging.debug("readResponse..............Reading.")
                sleep(DEFAULT_DELAY)
                response = self.PN532.transaction(
                    reading(self.address, 255))
                logging.debug(response)
                logging.debug("readResponse..............Read.")                        
                
                frame = Pn532Frame.from_response(response)

                # Acknowledge Data frames coming from the PN532
                if frame.get_frame_type() == PN532_FRAME_TYPE_DATA:
                   self.send_command(Pn532Frame(
                   frame_type=PN532_FRAME_TYPE_ACK))

             except TimeoutException:
                logging.debug('Timeout')
                return False
             except InvalidResponseException :
                logging.debug("Invalid Response")
                c_retry+=1
             else :
                if timeout :                
                  signal.alarm(0)
                return frame
            
    def send_command(self, frame,retry = 3):
        """Sends a command frame to the PN532.

        Arguments:
        @param[in]  frame   Pn532Frame to send.

        """
        logging.debug("send_command...")
        c_retry = 0
        while c_retry < retry:
            try:
                logging.debug("send_command...........Sending.")

                sleep(DEFAULT_DELAY)                
                self.PN532.transaction(
                    writing(self.address, frame.to_tuple()))                
                logging.debug(frame.to_tuple())

                logging.debug("send_command...........Sent.")
            except Exception as ex:
                logging.debug(ex)
                sleep(DEFAULT_DELAY)
            else:
                return True

    def read_ack(self):
        """Wait for a valid ACK frame to be returned."""
        logging.debug("read_ack...")

        retry = 0
        
        while retry < 5:
            sleep(DEFAULT_DELAY)
            response_frame = self.read_response()

            if response_frame.get_frame_type() == PN532_FRAME_TYPE_ACK:
                return True
            else:
                return False        

    def get_uid(self,timeout=False) :
        frame = self.read_mifare(timeout)
        if not frame :
            return False
        
        response = frame.get_data()        
        #if response[0] != 0x01:
        #    raise RuntimeError('More than one card detected!')
        if response[6] > 0x07:
            #raise RuntimeError('Found card with unexpectedly long UID!')
            return False
        # Return UID of card.
        return response[7:7+response[6]]
    
    def read_mifare(self,timeout=False):
        """Wait for a MiFARE card to be in the PN532's field, and read it's UID."""
        
        frame = Pn532Frame(frame_type=PN532_FRAME_TYPE_DATA, data=bytearray([PN532_COMMAND_INLISTPASSIVETARGET, 0x01, 0x00]))
        self.send_command_check_ack(frame)

        return self.read_response()

    def reset_i2c(self):
        """Reset the I2C communication connection."""
        logging.debug("I2C Reset...")

        self.PN532.close()
        del self.PN532
        self.PN532 = I2CMaster(self.i2c_channel)

        logging.debug("I2C Reset............Created.")

    def SAMconfigure(self, frame=None):
        """Send a SAMCONFIGURATION command to the PN532.

        Arguments:
        @param[in]  frame   Custom SAMconfigure options can be passed here.

        """
        if frame is None:
            frame = Pn532Frame(frame_type=PN532_FRAME_TYPE_DATA,
                               data=bytearray(
                                   [PN532_COMMAND_SAMCONFIGURATION,
                                    PN532_SAMCONFIGURATION_MODE_NORMAL,
                                    PN532_SAMCONFIGURATION_TIMEOUT_50MS,
                                    PN532_SAMCONFIGURATION_IRQ_ON]))

        self.send_command_check_ack(frame)
                

    def __exit__(self, type, value, traceback):
        """Make sure the I2C communication channel is closed."""
        self.PN532.close()
        del self.PN532
