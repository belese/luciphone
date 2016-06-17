from modules.py532lib.NFC import NFC as NFC


print ('Write UID')
#write .UID in current dir
UID_FILE = ".UID"

def write_uid(uid):
    f = open(UID_FILE,'w')
    print("Write UID : %s"%str(uid))
    uid = f.write(str(uid))
    f.close
    NFC.stop()

def stop(uid):
    NFC.stop()
NFC.add_event_detect(NFC.NEWTAG,write_uid)
NFC.add_event_detect(NFC.REMOVETAG,stop)

print('Put the disk on plate')
NFC.start()
