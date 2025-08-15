"""
Agent factory for creating and managing agent instances.
Inspired by FoodSave AI's AgentFactory pattern.
"""
import logging
from typing import Any, Dict, List, Optional, Type

from ..interfaces import AgentFactoryInterface, BaseAgentInterface
from .agents import OllamaAgent, RouterAgent
from ..models import Agent

logger = logging.getLogger(__name__)


class AgentFactory(AgentFactoryInterface):
    """
    Factory for creating agent instances with database integration.
    """
    
    # Registry of available agent classes
    _agent_registry: Dict[str, Type[BaseAgentInterface]] = {
        'router': RouterAgent,
        'ollama': OllamaAgent, # Keep for backward compatibility
    }
    
    def __init__(self):
        self._instances: Dict[str, BaseAgentInterface] = {}
    
    def register_agent(self, agent_type: str, agent_class: Type[BaseAgentInterface]):
        """Register new agent type"""
        self._agent_registry[agent_type] = agent_class
        logger.info(f"Registered agent type: {agent_type}")
    
    def create_agent(self, agent_type: str, **kwargs) -> BaseAgentInterface:
        """Create agent instance based on type"""
        if agent_type not in self._agent_registry:
            logger.error(f"Unknown agent type: {agent_type}")
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        agent_class = self._agent_registry[agent_type]
        
        try:
            agent_instance = agent_class(**kwargs)
            logger.info(f"Created agent of type: {agent_type}")
            return agent_instance
        except Exception as e:
            logger.error(f"Error creating agent {agent_type}: {str(e)}")
            raise
    
    async def create_agent_from_db(self, agent_name: str) -> BaseAgentInterface:
        """Create agent instance from database configuration"""
        try:
            from .async_services import AsyncAgentService
            
            # Use async service for database operations
            agent_config = await AsyncAgentService.get_agent_by_name(agent_name)
            
            # Prepare kwargs from database config
            kwargs = {
                'config': agent_config.config,
                'capabilities': agent_config.capabilities,
            }
            
            # Add specialized agent specific parameters
            if agent_config.agent_type == 'specialized':
                # Extract expertise area from config or use default
                expertise_area = agent_config.config.get('expertise_area', 'general')
                kwargs['expertise_area'] = expertise_area
            
            agent_instance = self.create_agent(agent_config.agent_type, **kwargs)
            
            # Set additional properties from database
            agent_instance.name = agent_config.name
            agent_instance.persona_prompt = agent_config.persona_prompt
            agent_instance.system_prompt = agent_config.system_prompt
            
            return agent_instance
            
        except Exception as e:
            logger.error(f"Error creating agent from database: {str(e)}")
            raise
    
    def list_available_agents(self) -> List[str]:
        """List all available agent types"""
        return list(self._agent_registry.keys())
    
    async def list_database_agents(self) -> List[Dict[str, Any]]:
        """List all agents from database"""
        try:
            from .async_services import AsyncAgentService
            return await AsyncAgentService.list_active_agents()
        except Exception as e:
            logger.error(f"Error listing database agents: {str(e)}")
            return []
    
    def get_or_create_instance(self, agent_type: str, instance_key: str, **kwargs) -> BaseAgentInterface:
        """Get existing instance or create new one"""
        if instance_key in self._instances:
            return self._instances[instance_key]
        
        agent_instance = self.create_agent(agent_type, **kwargs)
        self._instances[instance_key] = agent_instance
        return agent_instance
    
    def clear_instances(self):
        """Clear all cached instances"""
        self._instances.clear()
        logger.info("Cleared all agent instances")


# Global factory instance
agent_factory = AgentFactory()


# Convenience functions
async def get_agent_by_name(agent_name: str) -> BaseAgentInterface:
    """Get agent instance by name from database"""
    return await agent_factory.create_agent_from_db(agent_name)


def get_agent_by_type(agent_type: str, **kwargs) -> BaseAgentInterface:
    """Get agent instance by type"""
    return agent_factory.create_agent(agent_type, **kwargs)


async def list_available_agents() -> List[Dict[str, Any]]:
    """List all available agents from database"""
    return await agent_factory.list_database_agents()