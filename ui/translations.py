# Display-only catalog: source -> English, Traditional Chinese, Japanese, Korean.
# Business events and saved selections retain stable IDs across languages.
MESSAGES = {}
_ROWS = '''
提醒|Alerts|提醒|通知|알림
常规|General|一般|一般|일반
离席锁屏|Away lock|離席鎖定|離席時ロック|자리 비움 잠금
本人面容|Owner identity|本人面容|本人の顔|본인 얼굴
走动保护|Movement protection|走動保護|移動検出による保護|움직임 보호
浏览器裁剪|Browser clipping|瀏覽器裁剪|ブラウザーの切り抜き|브라우저 영역 자르기
启动与快捷键|Startup and shortcuts|啟動與快捷鍵|起動とショートカット|시작 및 단축키
退出时关闭所选窗口|Close selected window on exit|退出時關閉所選視窗|終了時に選択ウィンドウを閉じる|종료 시 선택한 창 닫기
仅真正退出时生效，收起到托盘不会关闭。|Only on exit; minimizing to the tray keeps it open.|僅真正退出時生效，收起至系統匣不會關閉。|アプリ終了時のみ適用。トレイに格納しても閉じません。|앱을 종료할 때만 적용됩니다. 트레이로 숨겨도 닫히지 않습니다.
无法关闭所选窗口，请重试或关闭“退出时关闭所选窗口”开关。|Cannot close the selected window. Retry or turn off Close selected window on exit.|無法關閉所選視窗，請重試或關閉「退出時關閉所選視窗」開關。|選択ウィンドウを閉じられません。再試行するか「終了時に選択ウィンドウを閉じる」をオフにしてください。|선택한 창을 닫을 수 없습니다. 다시 시도하거나 ‘종료 시 선택한 창 닫기’를 끄세요.
摄像头预览|Camera preview|攝影機預覽|カメラプレビュー|카메라 미리보기
重新选择本人|Select yourself again|重新選擇本人|本人を再選択|본인 다시 선택
收起到后台|Run in background|收起到背景|バックグラウンドへ|백그라운드로
本人已确认|Owner confirmed|本人已確認|本人を確認済み|본인 확인됨
尚未选择本人|Select yourself first|尚未選擇本人|本人を選択してください|본인을 선택하세요
隐藏画面|Hide preview|隱藏畫面|映像を隠す|화면 숨기기
显示画面|Show preview|顯示畫面|映像を表示|화면 표시
画面已隐藏|Preview hidden|畫面已隱藏|映像は非表示です|화면이 숨겨졌습니다
隐藏画面不影响监测|Monitoring continues while hidden|隱藏畫面不影響監測|非表示中も監視は続きます|숨겨도 감지는 계속됩니다
本机处理 · 不录制 · 不上传|Local only · No recording or uploads|本機處理 · 不錄製 · 不上傳|端末内で処理 · 録画・送信なし|기기 내 처리 · 녹화 및 업로드 안 함
隐藏浏览器顶部|Hide browser top|隱藏瀏覽器頂部|ブラウザー上部を隠す|브라우저 상단 숨기기
隐藏右侧滚动条|Hide right scrollbar|隱藏右側捲軸|右スクロールバーを隠す|오른쪽 스크롤바 숨기기
自动识别标签栏、地址栏和书签栏高度；滚轮仍可滚动。|Detect tab, address and bookmark bar heights automatically; mouse-wheel scrolling remains available.|自動識別分頁列、網址列和書籤列高度；滾輪仍可捲動。|タブ・アドレス・ブックマークバーの高さを自動取得。ホイール操作は引き続き使えます。|탭, 주소, 북마크 표시줄 높이를 자동 감지합니다. 마우스 휠 스크롤은 유지됩니다.
浏览器裁剪已关闭。|Browser clipping is off.|瀏覽器裁剪已關閉。|ブラウザーの切り抜きはオフです。|브라우저 영역 자르기가 꺼져 있습니다.
请选择浏览器窗口。|Select a browser window.|請選擇瀏覽器視窗。|ブラウザーのウィンドウを選択してください。|브라우저 창을 선택하세요.
未识别到浏览器区域，保留原窗口。|Browser area not detected; keeping the original window.|未識別到瀏覽器區域，保留原視窗。|ブラウザー領域を検出できないため、元の表示を維持します。|브라우저 영역을 감지하지 못해 원래 창을 유지합니다.
浏览器识别暂未响应，保留原窗口。|Browser detection timed out; keeping the original window.|瀏覽器識別暫未回應，保留原視窗。|ブラウザー検出が応答しないため、元の表示を維持します。|브라우저 감지가 응답하지 않아 원래 창을 유지합니다.
浏览器自动识别不可用，请重启程序。|Browser detection is unavailable. Restart the app.|瀏覽器自動識別無法使用，請重新啟動程式。|ブラウザー自動検出を利用できません。アプリを再起動してください。|브라우저 자동 감지를 사용할 수 없습니다. 앱을 다시 시작하세요.
浏览器区域裁剪已生效。|Browser clipping is active.|瀏覽器區域裁剪已生效。|ブラウザー領域の切り抜きが有効です。|브라우저 영역 자르기가 적용되었습니다.
无法恢复或调整浏览器背景。|Cannot restore or adjust the browser backdrop.|無法還原或調整瀏覽器背景。|ブラウザー背景を復元・調整できません。|브라우저 배경을 복원하거나 조정할 수 없습니다.
恢复浏览器裁剪失败，请重试。|Cannot restore the browser region. Try again.|還原瀏覽器裁剪失敗，請重試。|ブラウザー領域を復元できません。再試行してください。|브라우저 영역을 복원하지 못했습니다. 다시 시도하세요.
浏览器裁剪失败，请关闭开关后重试。|Browser clipping failed. Turn the switches off and try again.|瀏覽器裁剪失敗，請關閉開關後重試。|切り抜きに失敗しました。スイッチをオフにして再試行してください。|브라우저 영역 자르기에 실패했습니다. 스위치를 끈 후 다시 시도하세요.
返回面板|Back|返回面板|パネルへ戻る|패널로 돌아가기
选择目标窗口|Select a window|選擇目標視窗|対象ウィンドウを選択|대상 창 선택
取消选择|Clear selection|取消選擇|選択を解除|선택 해제
已取消选择目标窗口。|Target window selection cleared.|已取消選擇目標視窗。|対象ウィンドウの選択を解除しました。|대상 창 선택을 해제했습니다.
恢复窗口|Restore window|恢復視窗|ウィンドウを復元|창 복원
设置|Settings|設定|設定|설정
关闭|Close|關閉|閉じる|닫기
实时预览|Live preview|即時預覽|ライブプレビュー|실시간 미리보기
开启后选择本人 · 自动识别其他人员|Select yourself to detect others|啟用後選擇本人 · 自動辨識其他人員|開始後に自分を選択 · 他の人を自動検出|시작 후 본인 선택 · 다른 사람 자동 감지
未注册：双人脸提醒 · 已注册：其他人脸提醒|No enrollment: two faces · Enrolled: other faces|未註冊：雙人臉提醒 · 已註冊：其他人臉提醒|未登録：2人の顔 · 登録済み：他の顔|미등록: 두 얼굴 · 등록됨: 다른 얼굴
人员走动时提醒 · 请先选择本人|Alert on movement · select yourself first|有人走動時提醒 · 請先選擇本人|人の移動を通知 · まず本人を選択|사람이 움직일 때 알림 · 먼저 본인을 선택
先选择本人，再标记要忽略的同事|Select yourself, then mark coworkers to ignore|先選擇本人，再標記要忽略的同事|本人を選び、無視する同僚を指定|본인을 선택한 뒤 무시할 동료를 지정하세요
点同事框直接忽略 · 选择本人请点按钮|Click a coworker to ignore · use the button to select yourself|點同事框直接忽略 · 選擇本人請點按鈕|同僚の枠で無視 · 本人はボタンで選択|동료 상자를 눌러 무시 · 본인 선택은 버튼 사용
点击同事框直接忽略或取消忽略|Click a coworker to toggle ignore|點擊同事框直接忽略或取消忽略|同僚の枠で無視を切り替え|동료 상자를 눌러 무시 전환
走动提醒已开启 · 可标记忽略人员|Movement alerts active · you can ignore coworkers|走動提醒已開啟 · 可標記忽略人員|移動通知中 · 無視する人を指定可能|움직임 알림 켜짐 · 무시할 사람 지정 가능
选择本人|Select yourself|選擇本人|本人を選択|본인 선택
取消选择本人|Cancel owner selection|取消選擇本人|本人選択を取り消す|본인 선택 취소
请点击预览中的自己|Click yourself in the preview|請點擊預覽中的自己|プレビューの自分をクリック|미리보기에서 본인을 클릭하세요
请点击要忽略或取消忽略的同事|Click a coworker to toggle ignore|請點擊要忽略或取消忽略的同事|無視を切り替える同僚をクリック|무시 상태를 바꿀 동료를 클릭하세요
先点选择本人，再点预览中自己的检测框。|Select yourself, then click your detection box in the preview.|先點選擇本人，再點預覽中自己的偵測框。|「本人を選択」を押してから自分の枠をクリック。|본인 선택을 누른 뒤 미리보기의 본인 상자를 클릭하세요.
先点选择本人，再点自己的检测框；已注册可等待自动识别。|Select yourself, then click your box; enrolled users can wait for recognition.|先點選擇本人，再點自己的偵測框；已註冊可等待自動辨識。|本人を選んで自分の枠をクリック。登録済みなら自動認識を待てます。|본인 선택 후 본인 상자를 클릭하세요. 등록했다면 자동 인식을 기다리세요.
标记忽略人员|Ignore a person|標記忽略人員|無視する人を選択|무시할 사람 선택
取消标记|Cancel selection|取消標記|選択を取り消す|선택 취소
已忽略|Ignored|已忽略|無視中|무시됨
走动中|Moving|走動中|移動中|이동 중
静止|Still|靜止|静止中|정지
请选择其他人员|Select another person|請選擇其他人員|別の人を選択|다른 사람을 선택하세요
本人不能标记为忽略。|You cannot ignore yourself.|本人不能標記為忽略。|本人は無視できません。|본인은 무시할 수 없습니다.
请先选择本人|Select yourself first|請先選擇本人|まず本人を選択|먼저 본인을 선택하세요
点击预览中自己的检测框；已注册可等待自动识别。|Click your box in the preview; enrolled users can wait for recognition.|點擊預覽中自己的偵測框；已註冊可等待自動辨識。|プレビューの自分の枠を選択。登録済みなら自動認識を待てます。|미리보기에서 본인 상자를 선택하세요. 등록했다면 자동 인식을 기다리세요.
检测到人员走动|Person moving|偵測到人員走動|人の移動を検出|사람의 움직임 감지
画面中有其他人员持续移动。|Another person is moving across the frame.|畫面中有其他人員持續移動。|ほかの人が画面内を移動しています。|다른 사람이 화면에서 계속 움직입니다.
固定位置的同事不会触发提醒。|Stationary coworkers do not trigger alerts.|固定位置的同事不會觸發提醒。|動かない同僚は通知されません。|가만히 있는 동료는 알림을 보내지 않습니다.
点击「开始监测」；人脸注册可在设置中操作|Select Start; face enrollment is in Settings|點擊「開始監測」；可在設定中註冊人臉|開始を押してください。顔の登録は設定から行えます|시작을 누르세요. 얼굴 등록은 설정에서 할 수 있습니다
尚未开始监测|Monitoring not started|尚未開始監測|監視は未開始です|모니터링 시작 전
这是我|That's me|這是我|自分です|본인 선택
开始监测|Start|開始監測|監視を開始|모니터링 시작
暂停监测|Pause|暫停監測|監視を一時停止|모니터링 일시 중지
画面仅在本机内存中处理，不录制、不上传。|Frames stay in local memory. No recording or uploads.|畫面僅在本機記憶體中處理，不錄製、不上傳。|映像は端末のメモリ内で処理され、録画・送信されません。|영상은 로컬 메모리에서만 처리되며 녹화하거나 업로드하지 않습니다.
监测|Monitoring|監測|監視|모니터링
锁屏与本人|Lock & identity|鎖屏與本人|画面ロックと本人|화면 잠금 및 본인
摄像头工作模式|Camera mode|攝影機模式|カメラモード|카메라 모드
持续监测|Continuous monitoring|持續監測|常時監視|상시 모니터링
键鼠空闲后监测|Monitor after inactivity|鍵鼠閒置後監測|操作がない時に監視|입력 없을 때 모니터링
空闲后开启|Open after idle|閒置後開啟|待機後に起動|유휴 후 시작
在场复查间隔|Presence recheck interval|在場複查間隔|在席再確認間隔|재확인 간격
空闲模式会在连续确认有人在场 10 秒后关闭摄像头；恢复键鼠操作时立即关闭。|Idle mode closes the camera after 10 seconds of confirmed presence, or when input resumes.|閒置模式連續確認有人在場 10 秒後關閉攝影機；恢復鍵鼠操作時立即關閉。|待機モードでは在席を10秒確認した後、または操作再開時にカメラを閉じます。|유휴 모드는 10초간 재실을 확인하거나 입력이 재개되면 카메라를 닫습니다.
自动锁屏|Auto lock|自動鎖定螢幕|自動ロック|자동 잠금
连续离席且键鼠空闲 60 秒后，先提示 5 秒。|After 60 seconds away and idle, show a 5-second warning.|連續離席且鍵鼠閒置 60 秒後，先提示 5 秒。|離席と無操作が60秒続くと5秒間警告します。|60초간 부재 및 유휴 상태이면 5초간 경고합니다.
在场判断|Presence check|在場判斷|在席判定|재실 판단
任意人脸|Any face|任意人臉|任意の顔|모든 얼굴
仅本人|Only me|僅本人|本人のみ|본인만
即将锁屏 · {seconds} 秒|Locking in {seconds} s|即將鎖定螢幕 · {seconds} 秒|{seconds}秒後にロック|{seconds}초 후 잠금
窗口保护|Protection|視窗保護|ウィンドウ保護|창 보호
提醒与启动|Alerts & startup|提醒與啟動|通知と自動起動|알림 및 자동 실행
暂停监测快捷键|Pause monitoring shortcut|暫停監測快捷鍵|監視を一時停止するショートカット|모니터링 일시 중지 단축키
不启用|Disabled|停用|無効|사용 안 함
按组合键暂停监测；开启监测后仍需手动选择本人。|Press the shortcut to pause monitoring; start monitoring and select yourself manually.|按組合鍵暫停監測；開始監測後仍需手動選擇本人。|ショートカットで監視を一時停止します。開始後は手動で本人を選択してください。|단축키로 모니터링을 일시 중지합니다. 시작 후에는 본인을 직접 선택하세요.
快捷键不可用，可能已被其他程序占用。|Shortcut unavailable; another app may be using it.|快捷鍵無法使用，可能已被其他程式佔用。|ショートカットを使用できません。ほかのアプリが使用中の可能性があります。|단축키를 사용할 수 없습니다. 다른 앱에서 사용 중일 수 있습니다.
通用|General|一般|一般|일반
监测与保护设置仅本次运行有效；外观、语言、开机自启和更新偏好自动保存。|Monitoring and protection apply to this session; appearance, language, startup and update preferences are saved.|監測與保護設定僅本次執行有效；外觀、語言、開機自啟和更新偏好自動儲存。|監視・保護設定は今回のみ有効です。外観・言語・自動起動・更新設定は保存されます。|모니터링과 보호 설정은 현재 실행에만 적용됩니다. 모양, 언어, 자동 실행 및 업데이트 설정은 저장됩니다.
设置已自动保存；监测仍需手动启动并选择本人。|Settings are saved automatically; start monitoring and select yourself manually.|設定已自動儲存；監測仍需手動啟動並選擇本人。|設定は自動保存されます。監視の開始と本人の選択は手動で行ってください。|설정은 자동 저장됩니다. 모니터링을 시작하고 본인을 직접 선택하세요.
监测与保护设置仅本次运行有效；外观、语言和更新偏好自动保存。|Monitoring and protection apply to this session; appearance, language and update preferences are saved.|監測與保護設定僅本次執行有效；外觀、語言和更新偏好自動儲存。|監視・保護設定は今回のみ有効です。外観・言語・更新設定は保存されます。|모니터링과 보호 설정은 현재 실행에만 적용됩니다. 모양, 언어 및 업데이트 설정은 저장됩니다.
摄像头仅在开启监测时使用。|The camera is used only while monitoring.|攝影機僅在啟用監測時使用。|カメラは監視中のみ使用します。|카메라는 모니터링 중에만 사용됩니다.
摄像头|Camera|攝影機|カメラ|카메라
刷新设备|Refresh devices|重新整理裝置|デバイスを更新|장치 새로 고침
本人校准|Calibration|本人校準|本人の指定|본인 지정
点击预览中属于你的检测框。|Click your detection box in the preview.|點選預覽中屬於你的偵測框。|プレビューで自分の検出枠をクリックします。|미리보기에서 본인의 감지 상자를 클릭하세요.
返回校准|Calibrate|返回校準|本人を指定|본인 지정하기
人脸注册|Face enrollment|人臉註冊|顔の登録|얼굴 등록
注册当前本人|Enroll current owner|註冊目前本人|現在の本人を登録|현재 본인 등록
注册管理|Enrollment|註冊管理|登録管理|등록 관리
删除注册|Delete enrollment|刪除註冊|登録を削除|등록 삭제
已注册本人面容。|Your face is enrolled.|已註冊本人臉部。|本人の顔は登録済みです。|본인 얼굴이 등록되었습니다.
尚未注册本人面容。|No face is enrolled.|尚未註冊本人臉部。|顔は未登録です。|등록된 얼굴이 없습니다.
人脸特征仅保存在本机当前用户目录。|The face descriptor stays in this Windows user profile.|人臉特徵僅儲存在本機目前使用者目錄。|顔の特徴はこのユーザーの領域にのみ保存されます。|얼굴 특징은 현재 사용자 폴더에만 저장됩니다.
请先开始监测并在预览中选择本人。|Start monitoring and select yourself in the preview first.|請先開始監測並在預覽中選擇本人。|監視を開始し、プレビューで本人を選択してください。|먼저 감시를 시작하고 미리보기에서 본인을 선택하세요.
正在采集本人面容，请正对摄像头…|Capturing your face; look at the camera…|正在擷取本人臉部，請正對攝影機…|顔を取得中です。カメラを見てください…|얼굴을 수집 중입니다. 카메라를 정면으로 보세요…
本人面容已注册，后续启动将自动识别。|Face enrolled; future sessions will identify you automatically.|本人臉部已註冊，往後啟動將自動辨識。|顔を登録しました。次回から自動認識します。|얼굴이 등록되었습니다. 다음부터 자동 인식합니다.
注册失败：请正对摄像头并保持脸部清晰，再重试。|Enrollment failed. Face the camera with your face clearly visible, then retry.|註冊失敗：請正對攝影機並保持臉部清晰後重試。|登録に失敗しました。顔をはっきり映して再試行してください。|등록에 실패했습니다. 카메라를 정면으로 보고 다시 시도하세요.
注册失败：请确保画面中只有本人。|Enrollment failed. Make sure you are the only person visible.|註冊失敗：請確保畫面中只有本人。|登録に失敗しました。本人だけが映るようにしてください。|등록에 실패했습니다. 화면에 본인만 보이게 해주세요.
检测到未注册人脸|Unregistered face detected|偵測到未註冊人臉|未登録の顔を検出|등록되지 않은 얼굴 감지
检测到两张及以上人脸|Two or more faces detected|偵測到兩張以上人臉|2人以上の顔を検出|두 명 이상의 얼굴 감지
正在识别本人|Identifying you|正在辨識本人|本人を認識中|본인 인식 중
已发现注册者以外的人脸。|A face other than the enrolled user is visible.|已發現註冊者以外的人臉。|登録者以外の顔が映っています。|등록자 외의 얼굴이 보입니다.
也可手动选择本人用于窗口保护。|You can also select yourself for window protection.|也可手動選擇本人以啟用視窗保護。|ウィンドウ保護には手動で本人を選択できます。|창 보호를 위해 본인을 수동으로 선택할 수도 있습니다.
未检测到其他人脸。|No other face detected.|未偵測到其他人臉。|他の顔は検出されていません。|다른 얼굴이 감지되지 않았습니다.
画面中出现至少两张人脸。|At least two faces are visible.|畫面中出現至少兩張人臉。|2人以上の顔が映っています。|두 명 이상의 얼굴이 보입니다.
等待检测到至少两张人脸。|Waiting for at least two faces.|等待偵測到至少兩張人臉。|2人以上の顔を待機しています。|두 명 이상의 얼굴을 기다리는 중입니다.
开机自启|Launch at sign-in|登入時自動啟動|ログイン時に起動|로그인 시 실행
登录 Windows 后自动运行 BehindWatch。|Run BehindWatch when you sign in to Windows.|登入 Windows 後自動執行 BehindWatch。|Windows にサインインしたときに BehindWatch を起動します。|Windows 로그인 시 BehindWatch를 실행합니다.
开机自启设置失败：{error}|Could not set launch at sign-in: {error}|無法設定登入時自動啟動：{error}|自動起動を設定できません：{error}|로그인 시 실행을 설정하지 못했습니다: {error}
{app} 已在运行。|{app} is already running.|{app} 已在執行。|{app} は既に実行中です。|{app}이(가) 이미 실행 중입니다.
只保护所选窗口，恢复后关闭自动隐藏。|Only the selected window is protected. Restoring disables auto-hide.|僅保護所選視窗，恢復後關閉自動隱藏。|選択したウィンドウのみ保護します。復元すると自動非表示を解除します。|선택한 창만 보호합니다. 복원하면 자동 숨기기가 꺼집니다.
目标窗口|Target window|目標視窗|対象ウィンドウ|대상 창
刷新窗口|Refresh windows|重新整理視窗|ウィンドウを更新|창 새로 고침
自动隐藏|Auto-hide|自動隱藏|自動非表示|자동 숨기기
其他人员出现时隐藏窗口|Hide when another person appears|其他人員出現時隱藏視窗|他の人が現れたら非表示|다른 사람이 나타나면 창 숨기기
其他人员走动时隐藏窗口|Hide when another person moves|其他人員走動時隱藏視窗|ほかの人が移動したら非表示|다른 사람이 움직이면 창 숨기기
鼠标透明度|Mouse opacity|滑鼠透明度|マウス連動の透明度|마우스 투명도
范围 0–255，0 为完全透明|Range 0–255; 0 is transparent|範圍 0–255，0 為完全透明|範囲 0～255、0 は完全透明|범위 0–255, 0은 완전 투명
移入|Mouse enters|移入|マウス進入時|마우스 진입
移出|Mouse leaves|移出|マウス退出時|마우스 이탈
选择目标窗口后开启；人员离开不会自动恢复。|Select a window to enable. People leaving will not restore it.|選擇目標視窗後啟用；人員離開不會自動恢復。|対象を選択して有効化します。人が離れても自動復元しません。|대상 창을 선택한 후 켜세요. 사람이 떠나도 자동 복원하지 않습니다.
恢复并关闭自动隐藏|Restore and disable auto-hide|恢復並關閉自動隱藏|復元して自動非表示を解除|복원 및 자동 숨기기 끄기
提醒方式|Alert style|提醒方式|通知方法|알림 방식
测试提醒|Test alert|測試提醒|通知をテスト|알림 테스트
测试提醒：检测到其他人员|Test alert: another person detected|測試提醒：偵測到其他人員|テスト通知：他の人物を検出しました|테스트 알림: 다른 사람이 감지되었습니다
测试提醒：检测到两张及以上人脸|Test alert: two or more faces detected|測試提醒：偵測到兩張以上人臉|テスト通知：2人以上の顔を検出|테스트 알림: 두 명 이상의 얼굴 감지
测试提醒：检测到人员走动|Test alert: person moving|測試提醒：偵測到人員走動|テスト通知：人の移動を検出|테스트 알림: 사람의 움직임 감지
系统状态|System status|系統狀態|システムの状態|시스템 상태
后台状态已更新|Background status updated|背景狀態已更新|バックグラウンドの状態を更新しました|백그라운드 상태가 업데이트되었습니다
有一项后台任务需要关注|A background task needs attention|有一項背景工作需要留意|バックグラウンドのタスクを確認してください|백그라운드 작업을 확인하세요
角落提示点|Corner dot|角落提示點|隅の通知ドット|모서리 알림 점
系统通知|System notification|系統通知|システム通知|시스템 알림
两种方式均保持静音，不抢占焦点。|Both options are silent and keep your keyboard focus.|兩種方式均保持靜音，不搶占焦點。|どちらも無音で、フォーカスを奪いません。|두 방식 모두 무음이며 포커스를 빼앗지 않습니다.
头部朝向仅供参考，不能确认阅读行为；遮挡或视野外可能漏检。|Head direction is an estimate, not evidence of reading. Occlusion and blind spots can cause missed detections.|頭部朝向僅供參考，不能確認閱讀行為；遮擋或視野外可能漏檢。|頭の向きは参考情報で、閲覧の証拠ではありません。遮蔽や視野外では検出できない場合があります。|머리 방향은 참고 정보이며 읽고 있음을 확인하지 못합니다. 가림이나 시야 밖에서는 감지하지 못할 수 있습니다.
外观与语言|Appearance & language|外觀與語言|外観と言語|모양 및 언어
跟随系统|System|跟隨系統|システムに従う|시스템 설정
浅色|Light|淺色|ライト|밝게
深色|Dark|深色|ダーク|어둡게
主题|Theme|主題|テーマ|테마
语言|Language|語言|言語|언어
版本更新|Updates|版本更新|更新|업데이트
当前版本|Current version|目前版本|現在のバージョン|현재 버전
开发版本|Development build|開發版本|開発版|개발 버전
自动检查更新|Automatic checks|自動檢查更新|更新を自動確認|자동 업데이트 확인
每天检查一次正式版本|Check stable releases daily|每天檢查一次正式版本|安定版を毎日確認|매일 정식 버전 확인
尚未检查更新|Updates not checked yet|尚未檢查更新|更新は未確認です|업데이트를 아직 확인하지 않았습니다
检查更新|Check for updates|檢查更新|更新を確認|업데이트 확인
打开下载页|Open downloads|開啟下載頁|ダウンロードページ|다운로드 페이지 열기
偏好保存失败：{error}|Could not save preferences: {error}|偏好儲存失敗：{error}|設定を保存できません：{error}|설정 저장 실패: {error}
正在检查更新…|Checking for updates…|正在檢查更新…|更新を確認中…|업데이트 확인 중…
检查失败：{error}|Check failed: {error}|檢查失敗：{error}|確認に失敗しました：{error}|확인 실패: {error}
暂无正式版本|No stable release available|暫無正式版本|正式版はまだありません|아직 정식 버전이 없습니다
可用版本：{version}|Available version: {version}|可用版本：{version}|利用可能なバージョン：{version}|사용 가능한 버전: {version}
已是最新版本|You're up to date|已是最新版本|最新バージョンです|최신 버전입니다
打开监测面板|Open monitoring panel|開啟監測面板|監視パネルを開く|모니터링 패널 열기
恢复窗口并关闭自动隐藏|Restore window and disable auto-hide|恢復視窗並關閉自動隱藏|ウィンドウを復元して自動非表示を解除|창 복원 및 자동 숨기기 끄기
退出|Quit|結束|終了|종료
知道了|Dismiss|知道了|閉じる|닫기
摄像头尚未开启|Camera is off|攝影機尚未啟用|カメラはオフです|카메라가 꺼져 있습니다
点击「开始监测」，选择画面中的自己完成校准|Start monitoring, then select yourself in the preview|點選「開始監測」，選擇畫面中的自己完成校準|監視を開始し、映像内の自分を選択してください|모니터링을 시작한 후 화면에서 본인을 선택하세요
本人|You|本人|本人|본인
人员 #{id}|Person #{id}|人員 #{id}|人物 #{id}|사람 #{id}
朝向屏幕附近|Facing near the screen|朝向螢幕附近|画面付近を向いている|화면 근처를 향함
朝向未确认|Direction unconfirmed|朝向未確認|向きは未確認|방향 미확인
鼠标透明度已启用；可与人员自动隐藏同时使用。|Mouse opacity enabled; can be used with auto-hide.|滑鼠透明度已啟用；可與人員自動隱藏同時使用。|マウス連動の透明度を有効にしました。自動非表示と併用できます。|마우스 투명도가 켜졌습니다. 자동 숨기기와 함께 사용할 수 있습니다.
鼠标透明度已开启，等待选择目标窗口。|Mouse opacity enabled; waiting for a target window.|滑鼠透明度已開啟，等待選擇目標視窗。|マウス連動の透明度は有効です。対象ウィンドウを選択してください。|마우스 투명도가 켜졌습니다. 대상 창을 선택하세요.
鼠标透明度已关闭，原透明度已还原。|Mouse opacity disabled; original opacity restored.|滑鼠透明度已關閉，原透明度已還原。|マウス連動を解除し、元の透明度に戻しました。|마우스 투명도가 꺼지고 원래 투명도가 복원되었습니다.
已选择窗口，勾选上方开关启用。|Window selected. Use the switches above to enable protection.|已選擇視窗，勾選上方開關啟用。|ウィンドウを選択しました。上のスイッチで有効化します。|창이 선택되었습니다. 위 스위치를 켜서 활성화하세요.
自动隐藏已开启，等待选择目标窗口。|Auto-hide enabled; waiting for a target window.|自動隱藏已啟用，等待選擇目標視窗。|自動非表示が有効です。対象を選択してください。|자동 숨기기가 켜졌습니다. 대상 창을 선택하세요.
已开启；开始监测并校准本人后生效。|Enabled; start monitoring and select yourself to activate.|已啟用；開始監測並校準本人後生效。|有効です。監視を開始して自分を指定すると動作します。|켜졌습니다. 모니터링을 시작하고 본인을 지정하면 적용됩니다.
已请求隐藏；可通过主界面或托盘恢复。|Hide requested; restore from the panel or tray.|已請求隱藏；可透過主介面或系統匣恢復。|非表示を要求しました。パネルまたはトレイから復元できます。|숨기기를 요청했습니다. 패널이나 트레이에서 복원할 수 있습니다.
自动隐藏已关闭；已请求恢复本次隐藏的窗口。|Auto-hide disabled; window restore requested.|自動隱藏已關閉；已請求恢復本次隱藏的視窗。|自動非表示を解除し、ウィンドウの復元を要求しました。|자동 숨기기를 끄고 창 복원을 요청했습니다.
未发现摄像头|No camera found|未找到攝影機|カメラが見つかりません|카메라를 찾을 수 없습니다
请连接摄像头，在设置中刷新设备。|Connect a camera and refresh devices in settings.|請連接攝影機，在設定中重新整理裝置。|カメラを接続し、設定でデバイスを更新してください。|카메라를 연결하고 설정에서 장치를 새로 고치세요.
运行依赖缺失|Missing dependencies|缺少執行相依套件|依存パッケージがありません|필수 패키지 누락
设备枚举失败|Device discovery failed|裝置列舉失敗|デバイス検出に失敗しました|장치 검색 실패
请选择摄像头|Select a camera|請選擇攝影機|カメラを選択してください|카메라를 선택하세요
在设置中连接并选择摄像头后再启动。|Connect and select a camera in settings before starting.|在設定中連接並選擇攝影機後再啟動。|設定でカメラを接続・選択してから開始してください。|설정에서 카메라를 연결하고 선택한 후 시작하세요.
正在启动|Starting|正在啟動|起動中|시작 중
加载本地模型并连接摄像头…|Loading local models and connecting the camera…|載入本機模型並連接攝影機…|ローカルモデルを読み込み、カメラに接続中…|로컬 모델 로드 및 카메라 연결 중…
正在暂停|Pausing|正在暫停|停止中|일시 중지 중
正在释放摄像头…|Releasing the camera…|正在釋放攝影機…|カメラを解放中…|카메라 해제 중…
摄像头已释放 · 画面不保留|Camera released · Frames discarded|攝影機已釋放 · 畫面不保留|カメラ解放済み · 映像は保持しません|카메라 해제됨 · 영상 저장 안 함
已暂停|Paused|已暫停|一時停止中|일시 중지됨
摄像头已释放，重新启动后需要校准。|Camera released. Select yourself again after restarting.|攝影機已釋放，重新啟動後需要校準。|カメラを解放しました。再開後に本人指定が必要です。|카메라가 해제되었습니다. 다시 시작하면 본인 지정이 필요합니다.
监测不可用|Monitoring unavailable|監測無法使用|監視を利用できません|모니터링 사용 불가
监测已中断，请检查摄像头或模型。|Monitoring interrupted. Check the camera or models.|監測已中斷，請檢查攝影機或模型。|監視が中断されました。カメラやモデルを確認してください。|모니터링이 중단되었습니다. 카메라나 모델을 확인하세요.
请重新选择本人|Select yourself again|請重新選擇本人|自分を再指定してください|본인을 다시 선택하세요
目标已离开画面。|The target has left the frame.|目標已離開畫面。|対象が映像から離れました。|대상이 화면에서 벗어났습니다.
需要本人校准|Select yourself|需要本人校準|本人を指定してください|본인 지정 필요
点击属于你的框，或选择人员编号再点“这是我”。|Click your box, or choose your ID and press “That's me”.|點選屬於你的框，或選擇人員編號再點「這是我」。|自分の枠をクリックするか、番号を選び「自分です」を押してください。|본인의 상자를 클릭하거나 번호를 선택한 후 본인 선택을 누르세요.
本人跟踪已丢失，请打开面板重新校准。|Tracking lost. Open the panel and select yourself again.|本人追蹤已遺失，請開啟面板重新校準。|本人の追跡が途切れました。パネルで再指定してください。|본인 추적이 끊겼습니다. 패널에서 다시 지정하세요.
检测到 {n} 位其他人员|{n} other people detected|偵測到 {n} 位其他人員|他の人物を {n} 人検出|다른 사람 {n}명 감지
监测运行中|Monitoring active|監測執行中|監視中|모니터링 중
持续分析人员活动和朝向。|Analyzing activity and head direction.|持續分析人員活動和朝向。|動きと頭の向きを分析中です。|사람의 움직임과 방향을 분석 중입니다.
当前画面未检测到其他人员。|No other people detected in the frame.|目前畫面未偵測到其他人員。|映像内に他の人物は検出されていません。|현재 화면에서 다른 사람이 감지되지 않았습니다.
{fps} 帧/秒  ·  镜像预览  ·  {n} 个可见目标|{fps} fps · Mirrored preview · {n} visible targets|{fps} 影格/秒 · 鏡像預覽 · {n} 個可見目標|{fps} fps · ミラー表示 · 対象 {n} 人|{fps} fps · 미러 미리보기 · 대상 {n}명
监测已超时|Monitoring timed out|監測已逾時|監視がタイムアウトしました|모니터링 시간 초과
长时间未收到新画面，请重新启动。|No recent frames received. Restart monitoring.|長時間未收到新畫面，請重新啟動。|映像を受信できません。監視を再開してください。|새 영상이 수신되지 않습니다. 다시 시작하세요.
监测超时，当前无法判断身后情况。|Monitoring timed out; surroundings cannot be assessed.|監測逾時，目前無法判斷身後情況。|監視がタイムアウトし、背後の状況を判断できません。|모니터링 시간이 초과되어 뒤쪽 상황을 판단할 수 없습니다.
监测异常退出|Monitoring stopped unexpectedly|監測異常結束|監視が予期せず終了しました|모니터링이 예기치 않게 종료됨
检测进程已结束，请重新启动。|Detection process ended. Restart monitoring.|偵測程序已結束，請重新啟動。|検出プロセスが終了しました。再開してください。|감지 프로세스가 종료되었습니다. 다시 시작하세요.
正在载入本地模型…|Loading local models…|正在載入本機模型…|ローカルモデルを読み込み中…|로컬 모델 로드 중…
正在打开摄像头…|Opening camera…|正在開啟攝影機…|カメラを起動中…|카메라 여는 중…
摄像头画面中断。监测已停止，请重新启动。|Camera stream interrupted. Monitoring stopped; please restart.|攝影機畫面中斷。監測已停止，請重新啟動。|映像が中断されました。監視を再開してください。|카메라 영상이 중단되었습니다. 모니터링을 다시 시작하세요.
有人可能看向屏幕|Someone may be looking at the screen|有人可能看向螢幕|誰かが画面を見ている可能性があります|누군가 화면을 보고 있을 수 있습니다
身后有人停留|Someone is lingering behind you|身後有人停留|背後に人が留まっています|뒤에 누군가 머물고 있습니다
身后有人活动|Someone is moving behind you|身後有人活動|背後で人が動いています|뒤에서 누군가 움직이고 있습니다
检测到其他人员|Another person detected|偵測到其他人員|他の人物を検出しました|다른 사람이 감지되었습니다
{message} · 人员 #{id}|{message} · Person #{id}|{message} · 人員 #{id}|{message} · 人物 #{id}|{message} · 사람 #{id}
'''
for _row in _ROWS.strip().splitlines():
    _source, *_values = _row.split('|')
    MESSAGES[_source] = tuple(_values)
_MORE = '''
无法读取窗口列表，请重试。|Cannot read window list. Try again.|無法讀取視窗清單，請重試。|ウィンドウ一覧を取得できません。再試行してください。|창 목록을 읽을 수 없습니다. 다시 시도하세요.
无法设置窗口透明度样式，请检查目标程序权限。|Cannot set opacity style. Check target app permissions.|無法設定視窗透明度樣式，請檢查目標程式權限。|透明度を設定できません。対象アプリの権限を確認してください。|투명도 스타일을 설정할 수 없습니다. 대상 앱 권한을 확인하세요.
目标窗口已关闭，请刷新并重新选择。|Target closed. Refresh and select another window.|目標視窗已關閉，請重新整理並重新選擇。|対象が閉じられました。更新して再選択してください。|대상 창이 닫혔습니다. 새로 고침 후 다시 선택하세요.
无法读取鼠标或窗口位置，请重试。|Cannot read pointer or window position. Try again.|無法讀取滑鼠或視窗位置，請重試。|マウスまたはウィンドウ位置を取得できません。|마우스 또는 창 위치를 읽을 수 없습니다. 다시 시도하세요.
该窗口的原透明度无法读取，未修改；请选择其他窗口。|Original opacity cannot be read. Nothing changed; select another window.|該視窗的原透明度無法讀取，未修改；請選擇其他視窗。|元の透明度を取得できないため変更していません。別の対象を選択してください。|원래 투명도를 읽을 수 없어 변경하지 않았습니다. 다른 창을 선택하세요.
无法设置透明度，请关闭透明度开关重试。|Cannot set opacity. Turn opacity off and try again.|無法設定透明度，請關閉透明度開關重試。|透明度を設定できません。スイッチを解除して再試行してください。|투명도를 설정할 수 없습니다. 스위치를 끄고 다시 시도하세요.
无法恢复原透明度，请重试。|Cannot restore original opacity. Try again.|無法恢復原透明度，請重試。|元の透明度を復元できません。再試行してください。|원래 투명도를 복원할 수 없습니다. 다시 시도하세요.
无法隐藏窗口，请检查目标程序权限后重试。|Cannot hide window. Check target permissions and try again.|無法隱藏視窗，請檢查目標程式權限後重試。|非表示にできません。対象の権限を確認してください。|창을 숨길 수 없습니다. 대상 앱 권한을 확인하고 다시 시도하세요.
无法恢复窗口，请重试；必要时重启目标程序。|Cannot restore window. Try again or restart the target app.|無法恢復視窗，請重試；必要時重新啟動目標程式。|復元できません。再試行し、必要なら対象アプリを再起動してください。|창을 복원할 수 없습니다. 다시 시도하거나 대상 앱을 다시 시작하세요.
{error}。请运行 launch.cmd 修复环境。|{error}. Run launch.cmd to repair the environment.|{error}。請執行 launch.cmd 修復環境。|{error}。launch.cmd で環境を修復してください。|{error}. launch.cmd를 실행하여 환경을 복구하세요.
'''
for _row in _MORE.strip().splitlines():
    _source, *_values = _row.split('|')
    MESSAGES[_source] = tuple(_values)

# 同系列共有界面文案直接复用 TokenMeter 翻译。
MESSAGES.update({'刷新': ('Refresh', '重新整理', '更新', '새로 고침'), '外观': ('Appearance', '外觀', '外観', '모양'), '外观主题': ('Theme', '外觀主題', 'テーマ', '테마'), '已自动保存': ('Saved', '已自動儲存', '保存済み', '저장됨'), '软件更新': ('Updates', '軟體更新', 'アップデート', '업데이트'), '自动检查': ('Automatic checks', '自動檢查', '自動確認', '자동 확인'), '更新通道': ('Channel', '更新通道', 'チャンネル', '업데이트 채널'), '正式版': ('Stable', '正式版', '安定版', '안정 버전'), '检查状态': ('Status', '檢查狀態', '状態', '상태'), 'GitHub 项目主页': ('GitHub project', 'GitHub 專案首頁', 'GitHub プロジェクト', 'GitHub 프로젝트'), '调整主题与面板外观，修改立即应用并保存。': ('Customize the theme and panel. Changes apply and save immediately.', '調整主題與面板外觀，修改立即套用並儲存。', 'テーマとパネルを調整します。変更はすぐに適用・保存されます。', '테마와 패널 모양을 조정합니다. 변경 사항은 즉시 적용 및 저장됩니다.'), '未保存': ('Not saved', '未儲存', '未保存', '저장 안 됨'), '切换到浅色主题': ('Switch to light theme', '切換至淺色主題', 'ライトテーマに切り替え', '밝은 테마로 전환'), '切换到深色主题': ('Switch to dark theme', '切換至深色主題', 'ダークテーマに切り替え', '어두운 테마로 전환'), '更新与关于': ('About', '更新與關於', '更新と情報', '업데이트 및 정보'), '管理版本更新，查看项目主页与反馈入口。': ('Manage updates and visit the project or feedback page.', '管理版本更新，查看專案首頁與意見回饋入口。', '更新を管理し、プロジェクトやフィードバックページを開きます。', '업데이트를 관리하고 프로젝트 및 피드백 페이지를 확인합니다.')})
MESSAGES['更新仅检查正式版本；下载后由你手动安装。'] = ('Only stable releases are checked; install downloads manually.', '更新僅檢查正式版本；下載後由你手動安裝。', '正式版のみ確認します。ダウンロード後は手動でインストールしてください。', '정식 버전만 확인합니다. 다운로드 후 수동으로 설치하세요.')
