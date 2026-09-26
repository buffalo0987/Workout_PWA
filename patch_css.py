with open("public/css/app.css", "r") as f:
    css = f.read()

css = css.replace("padding-bottom: 90px;", "padding-bottom: 20px;")
css += """
.hamburger-btn {
  background: none;
  border: none;
  color: var(--color-text);
  font-size: 1.6rem;
  cursor: pointer;
  line-height: 1;
}

.menu-item {
  background: none;
  border: none;
  color: var(--color-text);
  padding: 16px 20px;
  text-align: left;
  font-size: 1.1rem;
  width: 100%;
  border-bottom: 1px solid var(--color-card-border);
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-item:active {
  background: rgba(255,255,255,0.05);
}
"""
with open("public/css/app.css", "w") as f:
    f.write(css)
