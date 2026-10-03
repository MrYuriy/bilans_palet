// Login page.
if (token()) {
  location.href = "/app/pulpit";
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("login-msg");
  setMsg(msg, "");
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: {
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
      },
    });
    localStorage.setItem("token", data.access_token);
    location.href = data.user.must_change_password ? "/app/haslo" : "/app/pulpit";
  } catch (err) {
    setMsg(msg, err.message);
  }
});
