// Password change: forced after an admin set the password, or by choice.
(async () => {
  if (!token()) {
    location.href = "/";
    return;
  }
  const user = await api("/auth/me");
  if (user.must_change_password) {
    document.getElementById("password-why").textContent =
      "Hasło trzeba zmienić przed dalszą pracą.";
    document.getElementById("password-back").classList.add("hidden");
  }
  document.getElementById("password-logout").onclick = (e) => {
    e.preventDefault();
    logout();
  };

  document.getElementById("password-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("password-msg");
    const oldPwd = document.getElementById("old-password").value;
    const newPwd = document.getElementById("new-password").value;
    const newPwd2 = document.getElementById("new-password2").value;

    if (newPwd !== newPwd2) {
      setMsg(msg, "Nowe hasła nie są takie same");
      return;
    }
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: { old_password: oldPwd, new_password: newPwd },
      });
      location.href = "/app/pulpit";
    } catch (err) {
      setMsg(msg, err.message);
    }
  });
})();
