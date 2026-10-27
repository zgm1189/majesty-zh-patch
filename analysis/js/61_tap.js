// 尝试用 Android InputManager 注入触摸事件
Java.perform(function () {
  try {
    var InputManager = Java.use('android.hardware.input.InputManager');
    var im = InputManager.getInstance();
    var MotionEvent = Java.use('android.view.MotionEvent');
    var SystemClock = Java.use('android.os.SystemClock');
    var now = SystemClock.uptimeMillis();
    // 点横屏 (620,230)
    var down = MotionEvent.obtain(now, now, MotionEvent.ACTION_DOWN.value, 620, 230, 0);
    var up = MotionEvent.obtain(now, now + 80, MotionEvent.ACTION_UP.value, 620, 230, 0);
    var r1 = im.injectInputEvent(down, 0);
    var r2 = im.injectInputEvent(up, 0);
    send('inject down=' + r1 + ' up=' + r2);
  } catch (e) {
    send('err: ' + e);
  }
});
setTimeout(function () { send({ done: true }); }, 3000);
