// Shared shell of every /app page: who is signed in, which menu items they may
// use. Pages wait for App.ready before loading their data.

const ROLE_LABELS = { admin: "Administrator", operator: "Operator", viewer: "Podgląd" };

const App = {
  user: null,
  ready: null,
  // True when the user may use any of the given modules.
  can(...modules) {
    return !!this.user && modules.some((m) => this.user.permissions.includes(m));
  },
};

App.ready = (async () => {
  if (!token()) {
    location.href = "/";
    return new Promise(() => {}); // never resolves: the page is leaving
  }

  const user = await api("/auth/me");
  if (user.must_change_password && location.pathname !== "/app/haslo") {
    location.href = "/app/haslo";
    return new Promise(() => {});
  }
  App.user = user;

  const who = document.getElementById("who");
  if (who) {
    who.querySelector(".av").textContent = user.username.slice(0, 2);
    who.querySelector(".name").textContent = user.username;
    who.querySelector(".role").textContent = ROLE_LABELS[user.role] || user.role;
    who.querySelector(".out").onclick = logout;
  }

  // Menu items carry data-module="a b": shown when the user has any of them.
  document.querySelectorAll("[data-module]").forEach((el) => {
    el.classList.toggle("hidden", !App.can(...el.dataset.module.split(" ")));
  });

  const page = document.body.dataset.page;
  document.querySelectorAll(".nav a").forEach((a) => {
    a.classList.toggle("on", a.dataset.page === page);
  });

  return user;
})();
