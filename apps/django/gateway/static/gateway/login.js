function csrfToken() {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const error = document.getElementById("login-error");
  error.hidden = true;
  const response = await fetch("/api/v1/session/login/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify({ login: form.get("login"), password: form.get("password") }),
  });
  if (response.ok) {
    window.location.assign("/app/");
    return;
  }
  error.textContent = response.status === 429 ? "Trop de tentatives. Réessayez plus tard." : "Identifiant ou mot de passe incorrect.";
  error.hidden = false;
});
