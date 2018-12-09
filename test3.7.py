
#python2.7没有str格式，需要将其转化为bytes对象，可用.encode('utf8')转换。
#对于套接字中的对象，默认为bytes对象，通过str调用要转换为str对象，通过(.decode('utf8'))转换
#多用户链接
from asyncore import dispatcher     #聊天式协议
from asynchat import async_chat     #套接字
import socket,asyncore
 
#建立服务端端口和名称
PORT=5005
NAME='TestChat'
 
#异常处理
class EndSession(Exception): pass
 
#命令和参数传递调用
class CommandHandler:
    #未知命令，推送不存在
    def unknown(self,session,cmd):
        session.push('Unkonwn command: {}s\r\n'.format(cmd).encode('utf8'))
    #命令:say hello，读取say指令，hello作为参数，判断do_cmd是否存在，存在调用，不存在调用unknown
    def handle(self,session,line):
        if not line.strip(): return
        parts=line.split(' ',1)
        cmd=parts[0]
        try: line=parts[1].strip()
        except IndexError: line=''
        meth=getattr(self,'do_'+cmd,None)
        try:
            meth(session,line)
        except:
            self.unknown(session,cmd)
 
#房间模板
class Room(CommandHandler):
    #初始化服务器，初始化空会话列表
    def __init__(self,server):
        self.server=server
        self.sessions=[]
    #会话列表添加会话
    def add(self,session):
        self.sessions.append(session)
    #会话列表移除会话
    def remove(self,session):
        self.sessions.remove(session)
    #广播，对会话列表中全部会话推送文本
    def broadcast(self,line):
        for session in self.sessions:
            session.push(line)
    #登出时触发异常
    def do_logout(self,session,line):
        raise EndSession
 
#登陆房间
class LoginRoom(Room):
    #登陆时推送欢迎
    def add(self,session):
        Room.add(self,session)
        self.broadcast('Welcome to {}\r\n'.format(self.server.name).encode('utf8'))
    #未知命令
    def unknown(self,session,cmd):
        session.push('Please log in\nUse "login <nick>"\r\n'.encode('utf8'))
    #login方法：没输入，重新输入；名字在列表(任何房间)中，告知；没问题，确定会话名称，进入主房间
    def do_login(self,session,line):
        name=line.strip()
        if not name:
            session.push('Please enter a name\r\n'.encode('utf8'))
        elif name in self.server.users:
            session.push('The name "{}" is taken.\r\n'.format(name).encode('utf8'))
            session.push('Please try again.\r\n'.encode('utf8'))
        else:
            session.name=name
            session.enter(self.server.main_room)
 
#聊天室
class ChatRoom(Room):
    #进入时，推送欢迎信息，在服务器用户表中加入会话，调用room的add
    def add(self,session):
        self.broadcast((session.name+' has entered the room.\r\n').encode('utf8'))
        #users是一个字典
        self.server.users[session.name]=session
        super().add(session)
    #退出时，调用room中remove，推送离开信息
    def remove(self,session):
        Room.remove(self,session)
        self.broadcast((session.name+' has left the room.\r\n').encode('utf8'))
    #say方法：广播形式name: line
    def do_say(self,session,line):
        self.broadcast((session.name+': '+line+'\r\n').encode('utf8'))
    #look方法：同who方法
    def do_look(self,session,line):
        session.push('The following are logged in:\r\n'.encode('utf8'))
        for name in self.server.users:
            session.push((name + '\r\n').encode('utf8'))
    #who方法：对于用户列表，推送内部名称
    def do_who(self,session,line):
        session.push('The following are logged in:\r\n'.encode('utf8'))
        for name in self.server.users:
            session.push((name+'\r\n').encode('utf8'))
 
#登出房间
class LogoutRoom(Room):
    #删除用户列表中会话名称
    def add(self,session):
        try: del self.server.users[session.name]
        except KeyError: pass
 
#会话协议
class ChatSession(async_chat):
    #初始化套接字，定义终止符，设数据为空，进入登陆房间
    #conn=server+sock
    def __init__(self,server,sock):
        super().__init__(sock)
        self.server=server
        self.set_terminator(b"\r\n")
        self.data=[]
        self.name=None
        #使用服务器地址实例化登陆房间,并进入
        self.enter(LoginRoom(server))
    #进入房间：
    def enter(self,room):
        #退出现在房间，进入新房间
        try:cur=self.room
        except AttributeError: pass
        #try如果可以执行，则执行else中语句
        else: cur.remove(self)
        self.room=room
        room.add(self)
    #收集一定内容后，加入到data中
    def collect_incoming_data(self,data):
        self.data.append(data.decode('utf8'))
    #遇到换行符，将data放到line中，重置data，尝试对line进行方法调用，出现异常调用退出
    def found_terminator(self):
        line=''.join(self.data)
        self.data=[]
        try: self.room.handle(self,line)
        except EndSession: self.handle_close()
    #退出房间，进入登出房间
    def handle_close(self):
        async_chat.handle_close(self)
        self.enter(LogoutRoom(self.server))
 
#聊天服务器
class ChatServer(dispatcher):
    #实例化多用户连接和套接字，重用端口，打开端口，监听5长度队列，设置用户空字典，设置主房间为聊天室
    def __init__(self,port,name):
        super().__init__()
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('',port))
        self.listen(5)
        self.name=name
        self.users={}
        self.main_room=ChatRoom(self)
    #套接字链接，实例化会话
    def handle_accept(self):
        conn,addr=self.accept()
        ChatSession(self,conn)
 
if __name__=='__main__':
    #实例化聊天服务器
    s=ChatServer(PORT,NAME)
    #打开服务器
    try: asyncore.loop()
    #遇到输入中断，打印空行
    except KeyboardInterrupt: print()