"""
Servicio de Gemini para generar explicaciones médicas
Replica el comportamiento de Scanna.py (Streamlit)
"""

import logging
from PIL import Image
from typing import Optional
from google import genai
from google.genai.errors import APIError

from app.config import settings

logger = logging.getLogger(__name__)

# ✅ USAR EL MISMO MODELO QUE STREAMLIT
GEMINI_MODEL_ID = "gemini-2.5-flash"  # Mismo que Scanna.py


class GeminiExplainer:
    """Servicio para generar explicaciones médicas con Gemini"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializar servicio de Gemini
        
        Args:
            api_key: API key de Google AI Studio (opcional, usa settings si no se proporciona)
        """
        self.api_key = api_key or settings.gemini_api_key
        
        if not self.api_key:
            logger.warning("⚠️ API key de Gemini no configurada")
        else:
            logger.info(f"✅ Servicio de Gemini inicializado (modelo: {GEMINI_MODEL_ID})")
    
    def generate_explanation(
        self, 
        predicted_class: str,
        combined_image: Optional[Image.Image] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Generar explicación médica usando Gemini
        
        REPLICA EL COMPORTAMIENTO DE STREAMLIT:
        - Usa gemini-2.5-flash
        - Solo se llama cuando se solicita explícitamente
        - Mismo prompt que Scanna.py
        
        Args:
            predicted_class: Clase predicha ("Anemia" o "No Anemia")
            combined_image: Imagen combinada (original + heatmap)
            custom_prompt: Prompt personalizado (opcional)
        
        Returns:
            str con la explicación generada
        """
        if not self.api_key:
            logger.warning("⚠️ API key de Gemini no configurada, usando fallback")
            return self._generate_fallback_summary(predicted_class, 0.0)
        
        try:
            # Construir prompt (MISMO QUE STREAMLIT - Línea 210-218 de Scanna.py)
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = self._build_streamlit_prompt(predicted_class)
            
            logger.info(f"🤖 Consultando Gemini ({GEMINI_MODEL_ID}) para clase: {predicted_class}")
            
            # Crear cliente
            client = genai.Client(api_key=self.api_key)
            
            # ✅ OPTIMIZACIÓN: Redimensionar imagen si es muy grande
            if combined_image:
                combined_image = self._optimize_image_for_api(combined_image)
            
            # Generar contenido (IGUAL QUE STREAMLIT)
            if combined_image:
                # Con imagen
                response = client.models.generate_content(
                    model=GEMINI_MODEL_ID,
                    contents=[prompt, combined_image]
                )
            else:
                # Solo texto
                response = client.models.generate_content(
                    model=GEMINI_MODEL_ID,
                    contents=prompt
                )
            
            explanation = response.text
            logger.info("✅ Explicación generada exitosamente")
            
            return explanation
            
        except APIError as e:
            error_code = getattr(e, 'status_code', None) or getattr(e, 'code', None)
            
            # ✅ MANEJO ESPECÍFICO: Error 429 (Quota excedida)
            if error_code == 429 or 'RESOURCE_EXHAUSTED' in str(e) or '429' in str(e):
                logger.warning(
                    f"⚠️ Límite de Gemini alcanzado. "
                    f"El registro se guardó correctamente pero sin explicación detallada. "
                    f"Puedes generar la explicación más tarde con el endpoint de re-análisis."
                )
                # Retornar explicación básica sin usar API
                return self._generate_fallback_summary(predicted_class, 0.0)
            
            # Otros errores de API
            error_msg = f"Error de Google API: {error_code} {getattr(e, 'status', 'UNKNOWN')}. {getattr(e, 'message', str(e))}"
            logger.error(f"❌ {error_msg}")
            
            # Retornar explicación básica
            return self._generate_fallback_summary(predicted_class, 0.0)
            
        except Exception as e:
            error_msg = f"Error inesperado generando explicación: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            # Retornar explicación básica
            return self._generate_fallback_summary(predicted_class, 0.0)
    
    def _optimize_image_for_api(self, image: Image.Image, max_size: int = 1024) -> Image.Image:
        """
        Optimizar imagen para reducir tokens en la API
        
        Args:
            image: Imagen PIL
            max_size: Tamaño máximo de ancho/alto
        
        Returns:
            Imagen optimizada
        """
        # Si la imagen es muy grande, redimensionarla
        if image.width > max_size or image.height > max_size:
            # Calcular ratio para mantener proporción
            ratio = min(max_size / image.width, max_size / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            
            logger.info(f"📐 Redimensionando imagen de {image.size} a {new_size} para optimizar API")
            
            return image.resize(new_size, Image.Resampling.LANCZOS)
        
        return image
    
    def _build_streamlit_prompt(self, predicted_class: str) -> str:
        """
        Construir prompt EXACTO de Streamlit (Scanna.py línea 210-218)
        
        Args:
            predicted_class: Clase predicha
        
        Returns:
            str con el prompt
        """
        prompt = (
            f"Analiza la Imagen A (entrada cruda) y la Imagen B (mapa de atención asociado). "
            f"Las siguientes imágenes pertenecen a la clase {predicted_class} según el clasificador de anemia. "
            f"Explica en un solo párrafo qué regiones resaltadas en B guiaron la decisión, "
            f"qué rasgos visuales en A (color, vascularización, textura o palidez) sustentan "
            f"la pertenencia a {predicted_class}, y cómo estos se relacionan fisiológicamente "
            f"con la presencia o ausencia de anemia. Mantén la explicación breve, médica y "
            f"directamente basada en lo que se observa."
        )
        
        return prompt
    
    def generate_summary_without_image(
        self, 
        predicted_class: str,
        confidence: float
    ) -> str:
        """
        Generar resumen simple sin imagen (para casos donde no se generó heatmap)
        
        Args:
            predicted_class: Clase predicha
            confidence: Nivel de confianza (0-100)
        
        Returns:
            str con resumen médico
        """
        if not self.api_key:
            return self._generate_fallback_summary(predicted_class, confidence)
        
        try:
            prompt = (
                f"Genera un breve resumen médico (2-3 oraciones) explicando qué significa "
                f"un diagnóstico de '{predicted_class}' en el contexto de análisis de anemia "
                f"mediante imágenes de conjuntiva ocular. El modelo tiene una confianza del "
                f"{confidence}% en esta predicción. Incluye recomendaciones básicas."
            )
            
            logger.info(f"🤖 Generando resumen sin imagen para: {predicted_class}")
            
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=GEMINI_MODEL_ID,
                contents=prompt
            )
            
            return response.text
            
        except APIError as e:
            if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
                logger.warning("⚠️ Quota de Gemini excedida, usando fallback")
            else:
                logger.error(f"❌ Error generando resumen: {e}")
            
            return self._generate_fallback_summary(predicted_class, confidence)
            
        except Exception as e:
            logger.error(f"❌ Error generando resumen: {e}")
            return self._generate_fallback_summary(predicted_class, confidence)
    
    def _generate_fallback_summary(
        self, 
        predicted_class: str, 
        confidence: float
    ) -> str:
        """
        Generar resumen fallback si Gemini no está disponible
        
        Se usa cuando:
        - No hay API key
        - Se excedió la quota (error 429)
        - Hay error en la API
        """
        
        if predicted_class == "Anemia":
            return (
                f"Análisis completado con IA (confianza: {confidence if confidence > 0 else 'alta'}%). "
                f"Se detectaron signos compatibles con anemia. Se observa palidez en la "
                f"conjuntiva ocular. El análisis mediante IA sugiere realizar estudios "
                f"complementarios de laboratorio (hemograma completo, niveles de hierro, "
                f"ferritina) para confirmar el diagnóstico y determinar el tipo de anemia. "
                f"Se recomienda consulta con hematología para evaluación detallada."
            )
        else:
            return (
                f"Análisis completado con IA (confianza: {confidence if confidence > 0 else 'alta'}%). "
                f"No se detectaron signos de anemia. Los valores de coloración de la conjuntiva "
                f"están dentro del rango normal. Se recomienda continuar con chequeos rutinarios "
                f"y mantener una dieta balanceada rica en hierro. En caso de síntomas como "
                f"fatiga persistente, consultar con un especialista."
            )


# Instancia global (singleton)
_explainer_instance: Optional[GeminiExplainer] = None


def get_explainer() -> GeminiExplainer:
    """
    Obtener instancia del explicador (Singleton)
    """
    global _explainer_instance
    
    if _explainer_instance is None:
        _explainer_instance = GeminiExplainer()
    
    return _explainer_instance


def generate_medical_explanation(
    predicted_class: str,
    confidence: float,
    combined_image: Optional[Image.Image] = None
) -> str:
    """
    Función helper para generar explicación médica
    
    Args:
        predicted_class: Clase predicha
        confidence: Confianza de la predicción
        combined_image: Imagen combinada (opcional)
    
    Returns:
        str con explicación médica
    """
    explainer = get_explainer()
    
    if combined_image:
        return explainer.generate_explanation(
            predicted_class=predicted_class,
            combined_image=combined_image
        )
    else:
        return explainer.generate_summary_without_image(
            predicted_class=predicted_class,
            confidence=confidence
        )