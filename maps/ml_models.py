import os
import numpy as np
import pandas as pd
import logging
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Default models (will be replaced with trained models)
HEIGHT_MODEL = None
QUALITY_MODEL = None
SCALER = StandardScaler()


def predict_property_height(property):
    """Predict building height based on property attributes."""
    try:
        # In a real implementation, we'd use a trained model
        # For this demonstration, we'll use a simple heuristic
        if not property.building_area or not property.land_area:
            # If we don't have building and land area, use property type to estimate
            if property.property_type:
                if 'apartment' in property.property_type.lower() or 'condo' in property.property_type.lower():
                    return 15.0  # Typical apartment height (meters)
                elif 'commercial' in property.property_type.lower():
                    return 10.0  # Typical commercial building height
                elif 'house' in property.property_type.lower() or 'residential' in property.property_type.lower():
                    return 8.0  # Typical house height
                else:
                    return 9.0  # Default height
            else:
                return 9.0  # Default height if no property type
        else:
            # Calculate height based on building-to-land ratio and some assumptions
            ratio = property.building_area / property.land_area
            if ratio > 0.8:  # High density building (likely multi-story)
                stories = min(10, int(ratio * 10))  # Cap at 10 stories
            else:
                stories = max(1, int(ratio * 5))  # At least 1 story
                
            # Assume 3 meters per story
            return stories * 3.0
    
    except Exception as e:
        logger.error(f"Error predicting height for property {property.id}: {str(e)}")
        return None


def predict_property_quality(property):
    """Predict building quality/condition score (0-100)."""
    try:
        # In a real implementation, we'd use a trained model
        # For this demonstration, we'll use a simple heuristic
        
        base_score = 50  # Start with average score
        
        # Adjust based on age if available
        if property.year_built:
            current_year = 2023
            age = current_year - property.year_built
            
            # Newer buildings typically have better quality
            if age < 5:
                base_score += 30
            elif age < 10:
                base_score += 25
            elif age < 20:
                base_score += 15
            elif age < 30:
                base_score += 5
            elif age < 50:
                base_score -= 5
            elif age < 70:
                base_score -= 10
            else:
                base_score -= 15
        
        # Adjust based on property type
        if property.property_type:
            if 'luxury' in property.property_type.lower():
                base_score += 15
            elif 'commercial' in property.property_type.lower():
                base_score += 5
            elif 'industrial' in property.property_type.lower():
                base_score -= 5
        
        # Ensure score is within 0-100 range
        final_score = max(0, min(100, base_score))
        return final_score
    
    except Exception as e:
        logger.error(f"Error predicting quality for property {property.id}: {str(e)}")
        return None


def train_height_model(properties):
    """Train a model to predict building heights."""
    # This would be implemented with real training data
    # For demonstration, we'll create a simple linear regression model
    
    # In a real implementation, we would:
    # 1. Extract features from properties
    # 2. Normalize/standardize features
    # 3. Train a regression model
    # 4. Evaluate performance
    # 5. Save the trained model
    
    global HEIGHT_MODEL, SCALER
    
    try:
        # Get properties with both height and necessary features
        valid_properties = [p for p in properties if p.building_area and p.land_area and p.predicted_height]
        
        if len(valid_properties) < 10:
            logger.warning("Not enough data to train the height model (need at least 10 properties)")
            return None
        
        # Create feature matrix (X) and target vector (y)
        X = np.array([[p.building_area, p.land_area] for p in valid_properties])
        y = np.array([p.predicted_height for p in valid_properties])
        
        # Scale features
        SCALER = StandardScaler()
        X_scaled = SCALER.fit_transform(X)
        
        # Train model
        HEIGHT_MODEL = LinearRegression()
        HEIGHT_MODEL.fit(X_scaled, y)
        
        logger.info(f"Height model trained on {len(valid_properties)} properties")
        return HEIGHT_MODEL
    
    except Exception as e:
        logger.error(f"Error training height model: {str(e)}")
        return None


def train_quality_model(properties):
    """Train a model to predict building quality."""
    # This would be implemented with real training data
    # For demonstration, we'll create a simple random forest classifier
    
    # In a real implementation, we would:
    # 1. Extract features from properties
    # 2. Normalize/standardize features
    # 3. Train a classifier model
    # 4. Evaluate performance
    # 5. Save the trained model
    
    global QUALITY_MODEL
    
    try:
        # Get properties with both quality score and necessary features
        valid_properties = [p for p in properties if p.year_built and p.predicted_quality_score]
        
        if len(valid_properties) < 10:
            logger.warning("Not enough data to train the quality model (need at least 10 properties)")
            return None
        
        # For simplicity, we'll use year_built as the main feature
        # In a real model, we'd use more features
        X = np.array([[p.year_built] for p in valid_properties])
        
        # Convert quality scores to categories (0-20: poor, 21-40: fair, 41-60: average, 61-80: good, 81-100: excellent)
        categories = []
        for p in valid_properties:
            score = p.predicted_quality_score
            if score <= 20:
                categories.append(0)  # poor
            elif score <= 40:
                categories.append(1)  # fair
            elif score <= 60:
                categories.append(2)  # average
            elif score <= 80:
                categories.append(3)  # good
            else:
                categories.append(4)  # excellent
        
        y = np.array(categories)
        
        # Train model
        QUALITY_MODEL = RandomForestClassifier(n_estimators=10)
        QUALITY_MODEL.fit(X, y)
        
        logger.info(f"Quality model trained on {len(valid_properties)} properties")
        return QUALITY_MODEL
    
    except Exception as e:
        logger.error(f"Error training quality model: {str(e)}")
        return None
