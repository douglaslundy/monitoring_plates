import { PersonsManager } from "@/components/persons/PersonsManager";

export default function AdminPersonsPage() {
  return (
    <PersonsManager
      title="Pessoas"
      description="Cadastro de pessoas para reconhecimento facial (todos os clientes)"
    />
  );
}
