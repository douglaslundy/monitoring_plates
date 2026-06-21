import { PersonsManager } from "@/components/persons/PersonsManager";

export default function ClientPersonsPage() {
  return (
    <PersonsManager
      title="Pessoas"
      description="Cadastre pessoas para reconhecimento facial e alertas"
    />
  );
}
