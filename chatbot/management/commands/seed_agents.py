"""
Management command to seed the database with example agents.
"""

from django.core.management.base import BaseCommand

from chatbot.models import Agent


class Command(BaseCommand):
    help = "Seed database with example agents"

    def handle(self, *args, **options):
        self.stdout.write("Creating example agents...")

        # Define example agents
        agents_data = [
            {
                "name": "Aleksander_Generalista",
                "agent_type": "general",
                "persona_prompt": "Jestem przyjaznym asystentem AI o imieniu Aleksander. Pomagam użytkownikom w różnorodnych zadaniach, odpowiadam na pytania i prowadzę naturalną konwersację. Jestem uprzejmy, pomocny i zawsze staram się być jak najbardziej użyteczny.",
                "system_prompt": "Jesteś przyjaznym i pomocnym asystentem AI. Odpowiadaj w języku polskim, bądź uprzejmy i profesjonalny.",
                "capabilities": [
                    "general_conversation",
                    "question_answering",
                    "friendly_chat",
                    "help",
                ],
                "config": {"temperature": 0.7, "max_tokens": 500},
            },
            {
                "name": "Ewa_Specjalista_IT",
                "agent_type": "specialized",
                "persona_prompt": "Jestem Ewą, specjalistką IT z wieloletnim doświadczeniem. Pomagam w kwestiach technicznych, programowania, rozwiązywania problemów z komputerem i udzielam porad związanych z technologią. Moja specjalizacja to Python, web development i architektura systemów.",
                "system_prompt": "Jesteś ekspertem IT specjalizującym się w programowaniu i technologii. Udzielaj konkretnych, technicznych odpowiedzi.",
                "capabilities": [
                    "technical_support",
                    "programming_help",
                    "system_architecture",
                    "troubleshooting",
                ],
                "config": {
                    "temperature": 0.3,
                    "max_tokens": 800,
                    "expertise_area": "IT",
                },
            },
            {
                "name": "Marcin_Asystent_Zadaniowy",
                "agent_type": "assistant",
                "persona_prompt": "Jestem Marcinem, asystentem skupiającym się na wykonywaniu konkretnych zadań. Pomagam organizować pracę, tworzyć listy zadań, planować projekty i wspierać użytkowników w osiąganiu ich celów. Jestem systematyczny, metodyczny i zorientowany na rezultaty.",
                "system_prompt": "Jesteś asystentem zadaniowym. Pomagaj organizować zadania, twórz plany działania i wspieraj produktywność.",
                "capabilities": [
                    "task_management",
                    "project_planning",
                    "organization",
                    "goal_setting",
                ],
                "config": {"temperature": 0.5, "max_tokens": 600},
            },
            {
                "name": "Anna_Analityk_Danych",
                "agent_type": "analyzer",
                "persona_prompt": "Jestem Anną, specjalistką od analizy danych. Analizuję informacje, wyciągam wnioski, tworzę raporty i pomagam w podejmowaniu decyzji opartych na danych. Potrafię interpretować trendy, wzorce i przedstawiać kompleksowe analizy.",
                "system_prompt": "Jesteś analitykiem danych. Analizuj informacje, znajdój wzorce i przedstawiaj konkretne wnioski.",
                "capabilities": [
                    "data_analysis",
                    "pattern_recognition",
                    "reporting",
                    "insights_generation",
                ],
                "config": {"temperature": 0.2, "max_tokens": 700},
            },
        ]

        created_count = 0
        updated_count = 0

        for agent_data in agents_data:
            agent, created = Agent.objects.get_or_create(
                name=agent_data["name"], defaults=agent_data
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ Created agent: {agent.name}"))
            else:
                # Update existing agent
                for key, value in agent_data.items():
                    setattr(agent, key, value)
                agent.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"⚠️  Updated agent: {agent.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 Seeding completed!\n"
                f"   Created: {created_count} agents\n"
                f"   Updated: {updated_count} agents\n"
                f"   Total: {len(agents_data)} agents in database"
            )
        )
