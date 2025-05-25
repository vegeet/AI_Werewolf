function GameGoing() {
  setInterval(() => {
    fetch('http://localhost:5000/progress_game', {
      method: 'POST'
    })
      .then(response => response.json())
      .then(data => {
        if (data.success === false) {
          console.log(data.error);
          return;
        }

        if (window._hasProgressed) return;
        window._hasProgressed = true;

        const chatBox = document.getElementById('chat-box');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message system';
        messageDiv.textContent = data.message;
        chatBox.appendChild(messageDiv);

        messageDiv.offsetHeight;  // 触发 DOM 回流
        requestAnimationFrame(() => {
          chatBox.scrollTop = chatBox.scrollHeight;
        });
        // chatBox.scrollTop = chatBox.scrollHeight;

        setTimeout(() => {
          window.location.href = data.next;
        }, 2000);
      });
  }, 3000);  // 每3秒轮询一次
}


let gameOver = false;


function checkGameStatus() {
  if (gameOver) return; // 如果游戏已经结束，停止继续请求

  fetch("/game_status")
    .then(res => res.json())
    .then(data => {
      if (data.game_over) {
        gameOver = true;
        game_Over = true;
        showGameOverOverlay(data.message);
        // 游戏结束返回room.html页面

        setTimeout(() => {
          window.location.href = data.redirect_url || "/room";
        }, 3000);
      }
    })
    .catch(err => console.error("状态检查失败", err));
}

// 每5秒检查一次游戏状态
setInterval(checkGameStatus, 5000);

// 显示游戏结束遮罩层
function showGameOverOverlay(message) {
  const overlay = document.createElement("div");
  overlay.style.position = "fixed";
  overlay.style.top = 0;
  overlay.style.left = 0;
  overlay.style.width = "100vw";
  overlay.style.height = "100vh";
  overlay.style.backgroundColor = "transparent"; // 透明背景
  overlay.style.display = "flex";
  overlay.style.justifyContent = "center";
  overlay.style.alignItems = "center";
  overlay.style.zIndex = 1000;

  const msgBox = document.createElement("div");
  msgBox.style.background = "rgba(255, 255, 255, 0.95)"; // 半透明白色背景
  msgBox.style.padding = "30px";
  msgBox.style.borderRadius = "10px";
  msgBox.style.fontSize = "24px";
  msgBox.style.fontWeight = "bold";
  msgBox.style.boxShadow = "0 0 20px rgba(0,0,0,0.5)";
  msgBox.innerText = message;

  overlay.appendChild(msgBox);
  document.body.appendChild(overlay);
}



function updateSystemMessages() {
  fetch('/get_messages')
    .then(res => res.json())
    .then(data => {
      const chatBox = document.getElementById('chat-box');
      if (!chatBox) return;

      chatBox.innerHTML = '';  // 清空旧消息
      data.messages.forEach(msg => {
        const div = document.createElement('div');
        div.className = msg.includes('说') ? 'chat-message player' : 'chat-message system';
        div.textContent = msg;
        chatBox.appendChild(div);
      });

      // 滚动到底部
      chatBox.offsetHeight;
      requestAnimationFrame(() => {
        chatBox.scrollTop = chatBox.scrollHeight;
      });
    })
    .catch(err => console.error('获取 system_messages 失败:', err));
}


let speechSubmitted = false;

function handleSpeechSubmit() {
  if (speechSubmitted) {
    alert("你已经提交过发言内容，不能重复提交。");
    return false;
  }

  const form = document.getElementById("speech-form");
  const input = document.getElementById("speech-input");
  const button = document.getElementById("speech-submit-btn");

  // 基本验证
  if (!input.value.trim()) {
    alert("请输入发言内容！");
    return false;
  }

  // 禁用按钮和隐藏表单
  button.disabled = true;
  speechSubmitted = true;

  // 隐藏整个发言区域
  form.style.display = "none";

  return true; // 继续提交
}

function handleVoteSubmit(form) {
    // 禁用所有投票按钮，防止重复提交
    document.querySelectorAll(".vote-button").forEach(btn => {
      btn.disabled = true;
      btn.innerText = "已投票";
    });

    return true; // 正常提交表单
  }
