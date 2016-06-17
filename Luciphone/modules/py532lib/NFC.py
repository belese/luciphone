import time
import sys,os

lib_path = os.path.abspath('./modules')
sys.path.append(lib_path)

from py532lib.i2c import *
from py532lib.frame import *
from py532lib.constants import *

class NFCmonitor :
   NEWTAG = 1
   REMOVETAG = 2

   def __init__(self) :
       self.cardIn = False       

       self.UUID = []
       self.stopped = False
       self.cbcardin = None
       self.cbcardout = None
       
       #Initialise NFC_reader
       self.pn532 = Pn532_i2c()
       self.pn532.SAMconfigure()
       
   def add_event_detect(self,fn,callback) :
      print ('new callback added')
      if fn == self.NEWTAG :
         self.cbcardin = callback
      elif fn == self.REMOVETAG :
         self.cbcardout = callback

   def _trust_uid(self,uid) :
       return uid == self.pn532.get_uid() and uid == self.pn532.get_uid() and uid == self.pn532.get_uid()
   
   def stop(self) :
       self.stopped = True

   def start(self) :       
       print ("NFC Monitor started")
       while not self.stopped :           
           uid = self.pn532.get_uid()
           if uid == self.UUID :             
             time.sleep(0.2)                                     
           elif uid and self._trust_uid(uid) :                
                print ("New Card Detected",uid)
                self.UUID = uid
                if not self.cardIn :
                    self.cardIn = True        
                if self.cbcardin : self.cbcardin(self.UUID)
                
           elif not uid and self.cardIn and self._trust_uid(uid):                              
                  print ("Card Removed")
                  uuid = self.UUID 
                  self.UUID = None
                  self.cardIn = False                  
                  if self.cbcardout : self.cbcardout(uuid)
           
                     
NFC = NFCmonitor()
