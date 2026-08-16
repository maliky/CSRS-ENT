import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "./router";

test("affiche la route de repli pour une URL inconnue", () => {
  render(
    <MemoryRouter initialEntries={["/page-inexistante"]}>
      <Routes>
        <Route path="/" element={<p>Accueil</p>} />
        <Route path="*" element={<p>Page indisponible</p>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(screen.getByText("Page indisponible")).toBeInTheDocument();
  expect(screen.queryByText("Accueil")).not.toBeInTheDocument();
});
