"""Singleton 패턴 유틸리티"""

from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, TypeVar

T = TypeVar('T')


class SingletonRegistry:
  """
  파라미터별 Singleton 인스턴스를 관리하는 레지스트리

  각 클래스-파라미터 조합마다 하나의 인스턴스만 유지합니다.
  """
  _instances: Dict[tuple, Any] = {}

  @classmethod
  def get_instance(
      cls,
      class_type: Type[T],
      key_param: Optional[str] = None,
      *args,
      **kwargs
  ) -> T:
    """
    Singleton 인스턴스를 가져오거나 생성합니다.

    Args:
        class_type: 생성할 클래스 타입
        key_param: 키로 사용할 파라미터의 이름 (예: "ai_provider_type")
                   None이면 클래스 타입만으로 판단
        *args, **kwargs: 클래스 생성자 인자

    Returns:
        Singleton 인스턴스

    Example:
        >>> manager = SingletonRegistry.get_instance(
        ...     WorkLogManager,
        ...     key_param="ai_provider_type",
        ...     ai_provider_type="claude"
        ... )
    """
    # Create key
    if key_param and key_param in kwargs:
      key = (class_type, kwargs[key_param])
    else:
      key = (class_type,)

    # Get or create instance
    if key not in cls._instances:
      cls._instances[key] = class_type(*args, **kwargs)

    return cls._instances[key]

  @classmethod
  def clear(cls) -> None:
    """모든 인스턴스를 클리어합니다 (테스트용)"""
    cls._instances.clear()


def singleton_getter(
    class_type: Type[T],
    key_param: Optional[str] = None
) -> Callable[..., T]:
  """
  Singleton getter 함수를 생성합니다.

  Args:
      class_type: 생성할 클래스 타입
      key_param: 키로 사용할 파라미터의 이름

  Returns:
      Singleton 인스턴스를 반환하는 getter 함수

  Example:
      >>> get_work_log_manager = singleton_getter(
      ...     WorkLogManager,
      ...     key_param="ai_provider_type"
      ... )
      >>> manager = get_work_log_manager(ai_provider_type="claude")
  """
  @wraps(class_type.__init__)
  def getter(*args, **kwargs) -> T:
    return SingletonRegistry.get_instance(
        class_type,
        key_param=key_param,
        *args,
        **kwargs
    )

  return getter


# Legacy support: 기존 패턴을 위한 간단한 싱글톤 관리
class SimpleSingleton:
  """
  단일 파라미터 기반 Singleton 패턴 (기존 코드 호환용)

  이 패턴은 마지막으로 요청된 파라미터의 인스턴스만 유지합니다.
  """
  def __init__(self, class_type: Type[T], param_name: str = "ai_provider_type"):
    self.class_type = class_type
    self.param_name = param_name
    self._instance: Optional[T] = None
    self._last_param: Optional[str] = None

  def get(self, **kwargs) -> T:
    """
    Singleton 인스턴스를 가져오거나 생성합니다.

    Args:
        **kwargs: 클래스 생성자 인자

    Returns:
        Singleton 인스턴스
    """
    param_value = kwargs.get(self.param_name)

    # Create new instance if:
    # 1. No instance exists, or
    # 2. Parameter value changed
    if self._instance is None or self._last_param != param_value:
      self._instance = self.class_type(**kwargs)
      self._last_param = param_value

    return self._instance
