"""Generate exact, editable SVG and high-resolution PNG schematic reference sheets.
These are drawing artifacts, not an EDA netlist or a fabricated PCB design.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import csv, json
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / 'schematic_images'
OUT.mkdir(parents=True, exist_ok=True)
SCALE = 2
INK, WIRE, BLUE, RED, GRAY = '#192b3d', '#14734a', '#1458a0', '#b53b32', '#637180'
FONTS = {'normal': r'C:\Windows\Fonts\msyh.ttc', 'bold': r'C:\Windows\Fonts\msyhbd.ttc'}
BOM, CONNECTIONS = [], []

class Page:
    def __init__(self, number, title, subtitle):
        self.name = f'{number:02d}_'+['主控排针','电源与模拟采样','MAX7219电平转换','十二路按钮','换向与辅助输入'][number-1]
        self.im = Image.new('RGB', (3200,2200), 'white')
        self.d = ImageDraw.Draw(self.im)
        self.svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="3200" height="2200" viewBox="0 0 1600 1100">', '<rect width="1600" height="1100" fill="white"/>']
        self.rect(30,25,1570,1070,GRAY)
        self.text(60,47,f'JR 单手柄控制器 / {title}',30,INK,True)
        self.text(60,96,subtitle,17,GRAY)
        self.line(55,132,1545,132,GRAY)
        self.line(55,1020,1545,1020,GRAY)
        self.text(65,1035,'Rev A1 · 2026-10-18 · 原理图录入参考 / 未经实物核对，不用于直接生产',16,RED)
        self.text(1400,1035,f'{number:02d} / 05',18,GRAY)
    def line(self,x1,y1,x2,y2,color=WIRE,width=2):
        self.d.line(tuple(int(v*SCALE) for v in (x1,y1,x2,y2)),fill=color,width=width*SCALE)
        self.svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>')
    def rect(self,x1,y1,x2,y2,color=INK,width=2):
        self.d.rectangle(tuple(int(v*SCALE) for v in (x1,y1,x2,y2)),outline=color,width=width*SCALE)
        self.svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    def text(self,x,y,t,size=18,color=INK,bold=False):
        font=ImageFont.truetype(FONTS['bold' if bold else 'normal'],size*SCALE)
        self.d.text((int(x*SCALE),int(y*SCALE)),t,font=font,fill=color)
        self.svg.append(f'<text x="{x}" y="{y+size}" font-family="Microsoft YaHei, sans-serif" font-size="{size}" font-weight="{"bold" if bold else "normal"}" fill="{color}">{escape(t)}</text>')
    def dot(self,x,y):
        self.d.ellipse(((x-3)*SCALE,(y-3)*SCALE,(x+3)*SCALE,(y+3)*SCALE),fill=WIRE)
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{WIRE}"/>')
    def net(self,x,y,t):
        self.text(x,y-24,t,17,BLUE)
    def ground(self,x,y):
        self.line(x,y,x,y+10)
        for dy,w in [(10,14),(16,9),(22,4)]: self.line(x-w,y+dy,x+w,y+dy)
    def r(self,ref,value,x,y,vertical=False):
        if vertical:
            self.line(x,y-30,x,y-19);self.rect(x-7,y-19,x+7,y+19);self.line(x,y+19,x,y+30)
            self.text(x+13,y-22,ref,15);self.text(x+13,y,value,15)
        else:
            self.line(x-50,y,x-30,y);self.rect(x-30,y-8,x+30,y+8);self.line(x+30,y,x+50,y)
            self.text(x-36,y-52,ref,15);self.text(x-36,y-31,value,15)
        BOM.append((ref,value,'Resistor', '0805'))
    def cap(self,ref,value,x,y):
        self.line(x,y-35,x,y-5);self.line(x-15,y-5,x+15,y-5);self.line(x-15,y+5,x+15,y+5);self.line(x,y+5,x,y+35)
        self.text(x+22,y-22,ref,16);self.text(x+22,y,value,16)
        BOM.append((ref,value,'Capacitor','0805 (voltage >= 10V for 5V rail)'))
    def connector(self,ref,title,x,y,n):
        self.text(x-20,y-68,ref,18,INK,True);self.text(x-20,y-42,title,16)
        self.rect(x,y-17,x+58,y+(n-1)*35+17)
        for i in range(n):
            yy=y+i*35;self.line(x-25,yy,x+15,yy);self.rect(x+15,yy-4,x+23,yy+4);self.text(x+31,yy-12,str(i+1),14)
        BOM.append((ref,title,f'Connector 1x{n}','TBD; verify actual connector'))
    def finish(self):
        self.im.save(OUT/(self.name+'.png'))
        (OUT/(self.name+'.svg')).write_text('\n'.join(self.svg+['</svg>']),encoding='utf-8')

def conn(ref,pin,net): CONNECTIONS.append((ref,str(pin),net))

# Sheet 1: actual candidate 22+22 header order from manufacturer reference.
p=Page(1,'主控板插座与网络','现有 S3 N16R8；此针序依据 YD 系列参考，排母脚号与板卡版本必须核对实物。')
left=[('3V3','+3V3'),('3V3','+3V3'),('EN','MCU_EN'),('GPIO4','BTN01'),('GPIO5','BTN02'),('GPIO6','BTN03'),('GPIO7','BTN04'),('GPIO15','BTN12'),('GPIO16','REV_F'),('GPIO17','REV_R'),('GPIO18','EB_SW'),('GPIO8','BTN05'),('GPIO3',None),('GPIO46',None),('GPIO9','BTN06'),('GPIO10','BTN07'),('GPIO11','BTN08'),('GPIO12','BTN09'),('GPIO13','BTN10'),('GPIO14','BTN11'),('5Vin',None),('GND','GND')]
right=[('GND','GND'),('GPIO43/TX','UART_TX'),('GPIO44/RX','UART_RX'),('GPIO1','ADC_MAIN'),('GPIO2','ADC_AUX'),('GPIO42',None),('GPIO41',None),('GPIO40','DISP_CS_3V3'),('GPIO39','DISP_CLK_3V3'),('GPIO38','DISP_DIN_3V3'),('GPIO37',None),('GPIO36',None),('GPIO35',None),('GPIO0','MCU_BOOT'),('GPIO45',None),('GPIO48',None),('GPIO47',None),('GPIO21','CAL_SW'),('GPIO20/USB_D+',None),('GPIO19/USB_D-',None),('GND','GND'),('GND','GND')]
for ref,x,rows,title in [('J1',130,left,'P1 / 候选左排 1×22 排母'),('J2',870,right,'P2 / 候选右排 1×22 排母')]:
    p.text(x,154,ref+'   '+title,21,INK,True)
    p.rect(x,196,x+260,862)
    for i,(name,net) in enumerate(rows):
        y=216+i*30;p.text(x+12,y-12,str(i+1).zfill(2),15,GRAY);p.text(x+57,y-12,name,17)
        p.line(x+237,y,x+310,y)
        if net:
            p.net(x+320,y+4,net);conn(ref,i+1,net)
        else:
            p.line(x+303,y-6,x+317,y+6,RED);p.line(x+303,y+6,x+317,y-6,RED)
            p.text(x+327,y-12,'不接载板',15,GRAY);conn(ref,i+1,'NC')
    BOM.append((ref,title,'Module socket','PENDING actual pitch / row spacing'))
p.text(90,890,'USB 使用主控板已有原生接口，GPIO19/20 不接载板线路。GPIO35/36/37 保留给板上存储器。',18)
p.text(90,930,'J1.21（5Vin）本版保持不接：独立的 +5V_DISP 绝不连接此脚，不短接 IN-OUT / USB-OTG 焊盘。',18,RED)
p.text(90,968,'NC 仅表示载板不连接，不代表主控板内部未使用。插座尺寸、朝向和编号未冻结。',17,GRAY)
p.finish()

# Sheet 2: display external supply, carrier decoupling, two independent ADC branches.
p=Page(2,'显示电源与两路模拟采样','显示独立 5V 电源；主控仍由原生 USB 供电。只共地，不合并正电源。')
p.connector('J90','显示电源输入',190,240,2)
p.line(165,240,105,240);p.net(65,236,'+5V_DISP')
p.line(165,275,125,275);p.ground(125,275)
conn('J90',1,'+5V_DISP');conn('J90',2,'GND')
for ref,val,x,rail in [('C1','10uF',430,'+5V_DISP'),('C2','100nF',650,'+5V_DISP'),('C3','1uF',1000,'+3V3'),('C4','100nF',1240,'+3V3')]:
    p.cap(ref,val,x,255);p.net(x-30,209,rail);p.line(x,211,x,220);p.ground(x,290);conn(ref,1,rail);conn(ref,2,'GND')
p.text(85,332,'+3V3 来自主控板 J1.1 / J1.2；GND 在全系统互连。J90 使用稳定的 5V，不接 3.3V。',17,RED)
for k,y,refj,gp in [(1,470,'J3','ADC_MAIN'),(2,750,'J4','ADC_AUX')]:
    rs,rw,cc=f'R{k*2-1}',f'R{k*2}',f'C{k+4}'
    p.text(85,y-95,('主手柄 / RK097N B10K 三脚款' if k==1 else '预留模拟输入 / 不用时连接器留空'),23,INK,True)
    p.connector(refj,'电位器线束',220,y,3)
    pv=f'POT{k}_V';ww=f'POT{k}_W'
    p.line(195,y,135,y);p.net(70,y,pv)
    p.line(195,y+35,120,y+35);p.net(65,y+37,ww)
    p.line(195,y+70,155,y+70);p.ground(155,y+70)
    p.net(390,y,'+3V3');p.line(410,y,480,y);p.r(rs,'4.7k',530,y);p.line(580,y,670,y);p.net(605,y,pv)
    p.net(810,y,ww);p.line(825,y,900,y);p.r(rw,'1k',950,y);p.line(1000,y,1280,y);p.net(1160,y,gp)
    p.dot(1070,y);p.line(1070,y,1070,y+15);p.cap(cc,'100nF',1070,y+50);p.ground(1070,y+85)
    for pin,net in [(1,pv),(2,ww),(3,'GND')]:conn(refj,pin,net)
    for rr,nn in [(rs,('+3V3',pv)),(rw,(ww,gp)),(cc,(gp,'GND'))]:
        conn(rr,1,nn[0]);conn(rr,2,nn[1])
p.text(85,915,'外部电位器：J3.1 → 电阻轨一端；J3.2 → 滑动端；J3.3 → 电阻轨另一端。实物端子用万用表确认。',17)
p.text(85,949,'4.7k 与标称 10k 形成约 2.24V 供电；ADC 选择高衰减，按机械实际行程校准。100nF 靠近主控插座。',17)
p.text(85,980,'C1/C2 位于显示电源入口，C3/C4 位于载板 3V3 入口；储能与 USB 浪涌要在整机供电定稿时复核。',16,GRAY)
p.finish()

# Sheet 3: all 14 pins accounted for; three output channels + unused gate.
p=Page(3,'MAX7219 接口与电平转换','U1 = SN74AHCT125D（SOIC-14），VCC=5V；不要替换为 HC / AHC125。')
p.rect(600,220,930,870);p.text(620,240,'U1  SN74AHCT125D',22,INK,True)
p.text(640,275,'3.3V 输入 → 5V 输出',18,BLUE)
BOM.append(('U1','SN74AHCT125D','TTL-input buffer','SOIC-14_3.9x8.7mm_P1.27mm'))
for idx,y,ain,aout,net in [(1,350,2,3,'DIN'),(2,475,5,6,'CLK'),(3,600,9,8,'CS')]:
    ni=f'DISP_{net}_3V3';no=f'DISP_{net}_5V'
    p.net(100,y,ni);p.line(120,y,600,y);p.text(611,y-13,f'{ain}   {idx}A',18)
    p.text(830,y-13,f'{idx}Y   {aout}',18);p.line(930,y,1080,y);p.net(965,y,no)
    # All inputs held low if MCU absent/reset. Firmware establishes CS before clocks.
    p.dot(385,y);p.line(385,y,385,y+15);p.r(f'R{40+idx}','10k',385,y+45,True);p.ground(385,y+75)
    conn('U1',ain,ni);conn('U1',aout,no);conn(f'R{40+idx}',1,ni);conn(f'R{40+idx}',2,'GND')
for pin,y,nm in [(1,710,'1OE#'),(4,760,'2OE#'),(10,810,'3OE#')]:
    p.line(540,y,600,y);p.ground(540,y);p.text(613,y-13,f'{pin}   {nm}',18);conn('U1',pin,'GND')
p.line(750,175,750,220);p.net(690,175,'+5V_DISP');p.text(760,201,'14 VCC',16);conn('U1',14,'+5V_DISP')
p.line(750,870,750,900);p.ground(750,900);p.text(760,873,'7 GND',16);conn('U1',7,'GND')
p.cap('C7','100nF',1050,220);p.net(1010,180,'+5V_DISP');p.line(1050,181,1050,185);p.ground(1050,255);conn('C7',1,'+5V_DISP');conn('C7',2,'GND')
p.connector('J5','接 HS-F13A 输入侧',1340,350,5)
for i,net in enumerate(['+5V_DISP','GND','DISP_DIN_5V','DISP_CLK_5V','DISP_CS_5V']):
    yy=350+i*35;p.line(1315,yy,1170,yy);p.net(1150,yy,net);conn('J5',i+1,net)
p.text(1110,563,'模块实物针序可能不同，',17,RED);p.text(1110,589,'按 VCC/GND/DIN/CLK/CS 接线。',17,RED)
p.text(1110,625,'模块 DOUT 留空，不接回 S3。',17)
p.text(1110,690,'U1 第四路（未用）：',18,INK,True)
for pin,y,net in [(13,740,'+5V_DISP'),(12,790,'GND'),(11,840,None)]:
    p.text(840,y-13,f'{pin}',16);p.line(930,y,1050,y)
    if net:p.net(1060,y,net);conn('U1',pin,net)
    else:
        p.line(1044,y-6,1056,y+6,RED);p.line(1044,y+6,1056,y-6,RED);p.text(1065,y-13,'4Y 不连接',16);conn('U1',pin,'NC')
p.text(85,940,'OE# 接地启用前三路；未用 4OE# 接5V禁用，4A接地。C7 靠近 U1 的14/7脚。',18)
p.text(85,977,'输入默认下拉；固件先设置 DIN/CLK/CS，再初始化 MAX7219：关闭测试、清屏、低亮度、全8行扫描。',17,GRAY)
p.finish()

# Sheet 4: each complete button channel (no ambiguous repeated channel shorthand).
p=Page(4,'十二路独立按钮输入','外接常开按钮：按下=接地；GPIO 侧 10k 上拉，串联 330Ω。所有 GPIO 都是 3.3V 逻辑。')
functions=['警笛1','警笛2','ATS确认','EB复位','警报停止','定速/抑速','坡道起动','联络蜂鸣','暂停','视角','备用1','备用2']
for i in range(12):
    col,row=i//6,i%6;x=65+col*770;y=245+row*132;net=f'BTN{i+1:02d}';rpu=f'R{10+2*i}';rs=f'R{11+2*i}';j=f'J{10+i}'
    p.text(x,y-102,f'{i+1:02d}  {functions[i]}',19,INK,True)
    p.net(x,y,net);p.line(x+20,y,x+455,y);p.dot(x+200,y)
    # Erase wire interior via white shape before resistor placement.
    p.d.rectangle(((x+279)*2,(y-3)*2,(x+381)*2,(y+3)*2),fill='white')
    p.svg.append(f'<rect x="{x+279}" y="{y-3}" width="102" height="6" fill="white"/>')
    p.r(rs,'330R',x+330,y)
    p.line(x+200,y,x+200,y-20);p.r(rpu,'10k',x+200,y-50,True);p.net(x+155,y-86,'+3V3')
    p.connector(j,'常开触点',x+480,y,2)
    p.line(x+455,y+35,x+420,y+35);p.ground(x+420,y+35)
    for ref,pin,nn in [(rpu,1,'+3V3'),(rpu,2,net),(rs,1,net),(rs,2,net+'_EXT'),(j,1,net+'_EXT'),(j,2,'GND')]:conn(ref,pin,nn)
p.text(85,995,'J10–J21 是面板线束接口；各接口1脚接按钮，2脚接地。按钮无需外接电源；软件处理消抖和保持/释放。',16,GRAY)
p.finish()

# Sheet 5: dedicated reverser connector, EB and local calibration.
p=Page(5,'换向、EB、校准与测试点','接口输入逻辑与按钮相同；游戏换向中立与 EB/轴优先级要单独验证。')
p.text(85,160,'三位换向开关 / SPDT 中间断开',24,INK,True)
p.connector('J22','FWD / COM / REV',1140,300,3)
for net,y,rs,rpu,jpin in [('REV_F',300,'R50','R51',1),('REV_R',500,'R52','R53',3)]:
    p.net(100,y,net);p.line(120,y,400,y);p.r(rs,'330R',450,y);p.line(500,y,730,y);p.net(565,y,net+'_EXT')
    p.dot(300,y);p.line(300,y,300,y-30);p.r(rpu,'10k',300,y-60,True);p.net(250,y-95,'+3V3')
    yy=300+(jpin-1)*35;p.line(1115,yy,940,yy);p.net(930,yy,net+'_EXT')
    for ref,pin,nn in [(rs,1,net),(rs,2,net+'_EXT'),(rpu,1,'+3V3'),(rpu,2,net),( 'J22',jpin,net+'_EXT')]:conn(ref,pin,nn)
p.line(1115,335,1090,335);p.ground(1090,335);conn('J22',2,'GND')
p.text(920,430,'J22.2 接开关公共端；中间位两侧均断开。',17)
p.text(85,570,'独立 EB 触点 / 常开',23,INK,True)
p.net(100,720,'EB_SW');p.line(120,720,400,720);p.r('R54','330R',450,720);p.line(500,720,665,720)
p.dot(300,720);p.line(300,720,300,690);p.r('R55','10k',300,660,True);p.net(250,625,'+3V3')
p.connector('J23','EB触点',690,720,2);p.line(665,755,630,755);p.ground(630,755)
for r,pin,n in [('R54',1,'EB_SW'),('R54',2,'EB_EXT'),('R55',1,'+3V3'),('R55',2,'EB_SW'),('J23',1,'EB_EXT'),('J23',2,'GND')]:conn(r,pin,n)
p.text(900,570,'SW1 本地校准按钮 / 常开',23,INK,True)
p.net(920,720,'CAL_SW');p.line(940,720,1240,720);p.dot(1090,720)
p.line(1090,720,1090,690);p.r('R56','10k',1090,660,True);p.net(1040,625,'+3V3')
p.line(1240,720,1240,745);p.line(1240,775,1240,800);p.ground(1240,800)
p.line(1234,745,1246,745,INK);p.line(1234,775,1246,775,INK);p.line(1253,742,1253,766,INK);p.line(1253,754,1264,754,INK)
p.text(1280,735,'SW1',18);p.text(1280,765,'校准',16)
BOM.append(('SW1','CAL','Normally-open pushbutton','TBD'))
for r,pin,n in [('R56',1,'+3V3'),('R56',2,'CAL_SW'),('SW1',1,'CAL_SW'),('SW1',2,'GND')]:conn(r,pin,n)
p.text(85,835,'测试点（各自单焊盘，均不是短接跳线）',23,INK,True)
for i,net in enumerate(['GND','+3V3','+5V_DISP','ADC_MAIN','ADC_AUX','UART_TX','UART_RX','MCU_EN','MCU_BOOT']):
    x=100+i*160;p.dot(x,930);p.line(x,910,x,930);p.text(x-15,877,f'TP{i+1}',16);p.text(x-40,942,net,14,BLUE)
    BOM.append((f'TP{i+1}',net,'Test point','TestPoint_Pad_D1.5mm'));conn(f'TP{i+1}',1,net)
p.text(85,986,'独立 EB 不承担实车安全功能。MCU_EN / MCU_BOOT 仅作调试测试点，正常不连接或短接。',16,GRAY)
p.finish()

# Checks on the actual wiring inventory, not merely counts of drawing primitives.
seen={}
for ref,val,kind,foot in BOM:
    assert ref not in seen, f'Duplicate designator: {ref}'
    seen[ref]=(val,kind,foot)
pinmap={}
for ref,pin,net in CONNECTIONS:
    assert (ref,pin) not in pinmap, f'Duplicate pin: {ref}.{pin}'
    pinmap[ref,pin]=net
assert len([x for x in pinmap if x[0]=='U1'])==14
assert pinmap['U1','14']=='+5V_DISP' and pinmap['U1','7']=='GND'
assert pinmap['U1','1']==pinmap['U1','4']==pinmap['U1','10']=='GND'
assert pinmap['U1','13']=='+5V_DISP' and pinmap['U1','12']=='GND' and pinmap['U1','11']=='NC'
assert pinmap['J1','21']=='NC'
assert pinmap['J3','2']=='POT1_W' and pinmap['R2','2']=='ADC_MAIN'
assert pinmap['J2','10']=='DISP_DIN_3V3' and pinmap['U1','2']=='DISP_DIN_3V3'
assert pinmap['J2','9']=='DISP_CLK_3V3' and pinmap['U1','5']=='DISP_CLK_3V3'
assert pinmap['J2','8']=='DISP_CS_3V3' and pinmap['U1','9']=='DISP_CS_3V3'
for i in range(12):
    assert pinmap[f'J{10+i}','2']=='GND'
    assert pinmap[f'R{11+2*i}','1']==f'BTN{i+1:02d}'
for path,headers,rows in [(OUT/'BOM.csv',['Reference','Value','Type','Footprint_status'],BOM),(OUT/'connections.csv',['Reference','Pin','Net'],CONNECTIONS)]:
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(headers);w.writerows(rows)
(OUT/'verification.json').write_text(json.dumps({'status':'drawing-model connectivity checks passed','components':len(BOM),'pins':len(CONNECTIONS),'limitations':['Not an EDA netlist / no native ERC','Physical header assignment and dimensions pending','Existing board 5Vin left disconnected','Display powered by separate 5V supply, common ground only']},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Generated 5 PNG + 5 SVG sheets; {len(BOM)} components; {len(CONNECTIONS)} pin assignments. Connectivity assertions passed.')
