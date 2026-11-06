This is a library for developing software to input device information and acquire running status to TRAIN CREW.

*** Concept ***
The software for each device is not a plug-in, but an independent exe.
It is a mechanism to access TRAIN CREW by referring to TrainCrewInput.dll in the project and using its functions.

【TRAIN CREW(exe)】←→【TrainCrewInput.dll-Device Input/Output Software(exe)】

The reason is that the plug-in method was difficult to use with Unity, and the separate exe method allows you to create your own software to display the meters, etc.
At the moment, only the operation screen is supported, not the menu.

*** How to develop ***
Develop the software by adding TrainCrewInput.dll in the DLL folder as a reference.
The_simple_reference.htm file contains explanations of the functions.

By using TrainCrewInputDebugger.exe, you can test your software without starting TRAIN CREW.
(This feature has been implemented in TRAIN CREW since the Steam demo version, but will not be synchronized in the beta demo version on 6/5/2021)


*** Sample ***
A sample of the "master controller ii for train simulator" input is included.
Please run TSMasconInput.sln.
The exe will be generated in TSMasconInput\bin\Debug.
(You can check the operation by running TrainCrewInputDebugger.exe at the same time.)

Other simple samples with just buttons are included.

*** Notes ***
-Development requires knowledge of programming and other skills.
-Please be careful not to get into trouble with copyrights when creating the driver's cab instruments.
-TrainCrewInput.dll can be redistributed by bundling it with the developed software. However, please refrain from redistributing the entire folder of this development kit.
-If you want to use other libraries for communication with devices, please check the license of those libraries.
-Please do not analyze or change TrainCrewInput.dll.
-Mizotsuki Rail/Acty's responsibility is limited to the operation of the TRAINCREW input/output library (TrainCrewInput.dll).
-This software is designed to be developed in Visual Studio C#. Other development environments may not be supported.






**********************
original text

こちらはTRAIN CREWに対してデバイスの情報を入力したり走行状態を取得するためのソフトを開発するためのライブラリです。

＊概念
各デバイス用ソフトウェアはプラグインではなく独立したexeとなります。
プロジェクト内でTrainCrewInput.dllを参照し、その関数などを使用することでTRAIN CREWにアクセスできる仕組みになっています。

【TRAIN CREW(exe)】←→【TrainCrewInput.dll―デバイス入出力ソフトウェア(exe)】

プラグイン方式ではUnityでの動作に難があったこと、
別exe方式だと計器を表示するソフトを独自に作成できるなど柔軟性が上がることが理由です。

※今のところ運転画面のみ操作に対応しており、メニューの操作などには対応しておりません。

＊開発の仕方
DLLフォルダ内にあるTrainCrewInput.dllを参照に加えてソフトを開発してください。
簡易リファレンス.htmに関数などの説明を載せています。

TrainCrewInputDebugger.exeを使用することでTRAIN CREWを起動しなくてもテストをすることができます。
（TRAIN CREW側はSteam体験版よりこの機能の実装しています。2021/6/5版のβ体験版では同期しません）


＊サンプル
TSマスコンの入力のサンプルを入れております。
TSMasconInput.slnを実行してください。
exeはTSMasconInput\bin\Debug内に生成されます。
（TrainCrewInputDebugger.exeと同時に起動することで動作確認ができます）

その他、ボタンだけのシンプルなサンプルを入れています。


＊注意事項
・開発にはプログラミングなどの知識が必要です。
・運転台計器などを作成する際は著作権などトラブルにならないよう配慮をお願いいたします。
・TrainCrewInput.dllは開発したソフトに同梱するなどの形で再配布可能です。ただし、この開発用キットのフォルダ丸ごとの再配布はご遠慮ください。
・デバイスとの通信用など他のライブラリ等も使用する際はそのライブラリ等のライセンスをご確認ください。
・TrainCrewInput.dllを解析・改変などはしないでください。
・溝月レイル/Actyが負う責任の範囲はTRAINCREW入出力ライブラリ(TrainCrewInput.dll)の動作までとし、各々のソフトウェアに起因する動作や公開後のトラブル等の責任は負いかねます。
・Visual　StudioのC#での開発を想定しています。その他の開発環境ではサポートできないことがあります。
