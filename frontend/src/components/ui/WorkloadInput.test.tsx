import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";
import { WorkloadInput } from "./WorkloadInput";

test("saisit la charge en heures par défaut sans transformer 1,5 en 1,05", async () => {
  const user = userEvent.setup();

  function Example() {
    const [days, setDays] = useState("1");
    return (
      <>
        <WorkloadInput
          id="charge"
          valueDays={days}
          hoursPerDay={8}
          onValueChange={setDays}
        />
        <output>{days}</output>
      </>
    );
  }

  render(<Example />);
  const input = screen.getByLabelText("Charge estimée");
  expect(input).toHaveValue(8);
  expect(screen.getByRole("combobox", { name: "Unité" })).toHaveValue("hours");

  await user.clear(input);
  await user.type(input, "1.5");

  expect(input).toHaveValue(1.5);
  expect(screen.getByText("0.1875")).toBeInTheDocument();
});

test("permet de choisir les jours ouvrés et conserve la valeur canonique", async () => {
  const user = userEvent.setup();
  const onValueChange = vi.fn();
  render(
    <WorkloadInput
      id="charge"
      valueDays="0.1875"
      hoursPerDay={8}
      onValueChange={onValueChange}
    />,
  );

  await user.selectOptions(screen.getByLabelText("Unité"), "days");

  expect(screen.getByLabelText("Charge estimée")).toHaveValue(0.1875);
  expect(screen.getByText("1 jour ouvré = 8 heures")).toBeInTheDocument();
});
