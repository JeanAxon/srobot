#include <Servo.h>
#include <math.h>

// ----------------------
// CONFIGURACIÓN DE SERVOS
// ----------------------
struct MotionProfile {
  bool active;             // Indica si el perfil está en ejecución
  float startAngle;        // Ángulo de inicio
  float targetAngle;       // Ángulo objetivo
  unsigned long startTime; // Momento de inicio (ms)
  unsigned long duration;  // Duración total (ms)
  float t_acc;             // Tiempo de aceleración (s)
  bool triangular;         // Perfil triangular (true) o trapezoidal (false)
  float vmax;              // Velocidad máxima efectiva (deg/s)
  float a;                 // Aceleración efectiva (deg/s^2)
};

Servo servos[6];
MotionProfile profiles[6];
const uint8_t servoPins[6] = {3, 5, 9, 6, 10, 11};

// Ángulos iniciales (todos a 90°)
float currentAngles[6] = {90, 90, 90, 90, 90, 90};
float targetAngles[6] = {90, 90, 90, 90, 90, 90};

// Velocidades máximas de cada servo (deg/s)
const float servoMaxDegPerSec[6] = {
  375.0,  // Servo 1: Base
  460.0,  // Servo 2: Hombro
  400.0,  // Servo 3: Codo
  400.0,  // Servo 4: Muñeca
  375.0,  // Servo 5: Giro del gripper
  375.0   // Servo 6: Apertura/Cierre del gripper
};

// Aceleraciones máximas (deg/s²) para cada servo
const float servoMaxAccel[6] = {
  300.0,  // Base
  300.0,  // Hombro
  300.0,  // Codo
  300.0,  // Muñeca
  300.0,  // Giro del gripper
  300.0   // Apertura/Cierre del gripper
};

uint8_t servoSpeed = 50; // Escala de 1 a 100 (se aplica a velocidad y aceleración)

// ----------------------
// CONFIGURACIÓN DEL MOTOR (Banda)
// ----------------------
const int dirPin = 2;
const int stepPin = 4;
bool motorActivo = false;
bool direccionDerecha = true;
unsigned long lastStepTime = 0;
unsigned long stepDelay = 2500;

// ----------------------
// FUNCIONES DE PLANIFICACIÓN DE MOVIMIENTO
// ----------------------
void iniciarMovimiento(int index, float target) {
  profiles[index].active = true;
  profiles[index].startAngle = currentAngles[index];
  profiles[index].targetAngle = target;
  profiles[index].startTime = millis();
  
  float delta = target - currentAngles[index];
  float d = fabs(delta);
  float sign = (delta >= 0) ? 1.0 : -1.0;
  
  // Determinar el servoSpeed efectivo: 100 para servos 3 y 4, servoSpeed para los demás
  uint8_t effectiveSpeed = (index == 2 || index == 3) ? 100 : servoSpeed;
  
  // Velocidad y aceleración efectivas según effectiveSpeed
  float vmax = servoMaxDegPerSec[index] * (effectiveSpeed / 100.0);
  float a = servoMaxAccel[index] * (effectiveSpeed / 100.0);
  
  profiles[index].vmax = vmax;
  profiles[index].a = a;
  
  // Tiempo para alcanzar vmax
  float t_acc = vmax / a;  // en segundos
  float d_acc = 0.5 * a * t_acc * t_acc;
  
  float T_total;    // Duración total en segundos
  bool triangular;  // Indicador de perfil triangular
  
  if (d < 2 * d_acc) {
    // Si la distancia es muy corta, no se alcanza vmax: perfil triangular
    t_acc = sqrt(d / a);
    T_total = 2 * t_acc;
    triangular = true;
  } else {
    // Perfil trapezoidal: fase de aceleración, velocidad constante y desaceleración
    float d_const = d - 2 * d_acc;
    float t_const = d_const / vmax;
    T_total = 2 * t_acc + t_const;
    triangular = false;
  }
  
  profiles[index].t_acc = t_acc;
  profiles[index].duration = max((unsigned long)(T_total * 1000), 100UL);
  profiles[index].triangular = triangular;
  
  targetAngles[index] = target;
}

float calcularPosicion(MotionProfile &profile, float t_elapsed) {
  float T_total = profile.duration / 1000.0;  // Convertir duración a segundos
  float d = fabs(profile.targetAngle - profile.startAngle);
  float sign = (profile.targetAngle >= profile.startAngle) ? 1.0 : -1.0;
  
  float pos = 0.0;
  float t_acc = profile.t_acc;
  float a = profile.a;
  float vmax = profile.vmax;
  
  if (profile.triangular) {
    // Perfil triangular
    if (t_elapsed < t_acc) {
      pos = 0.5 * a * t_elapsed * t_elapsed;
    } else {
      pos = d - 0.5 * a * (T_total - t_elapsed) * (T_total - t_elapsed);
    }
  } else {
    // Perfil trapezoidal
    float t_const = T_total - 2 * t_acc;
    if (t_elapsed < t_acc) {
      pos = 0.5 * a * t_elapsed * t_elapsed;
    } else if (t_elapsed < (t_acc + t_const)) {
      pos = 0.5 * a * t_acc * t_acc + vmax * (t_elapsed - t_acc);
    } else {
      float t_dec = t_elapsed - t_acc - t_const;
      pos = 0.5 * a * t_acc * t_acc + vmax * t_const + vmax * t_dec - 0.5 * a * t_dec * t_dec;
    }
  }
  
  if (pos > d) pos = d;
  return profile.startAngle + sign * pos;
}

void actualizarMovimientos() {
  unsigned long tNow = millis();
  for (int i = 0; i < 6; i++) {
    if (profiles[i].active) {
      float t_elapsed = (tNow - profiles[i].startTime) / 1000.0; // en segundos
      float T_total = profiles[i].duration / 1000.0;
      
      if (t_elapsed >= T_total) {
        currentAngles[i] = profiles[i].targetAngle;
        servos[i].write((int)(currentAngles[i] + 0.5));
        profiles[i].active = false;
      } else {
        float pos = calcularPosicion(profiles[i], t_elapsed);
        currentAngles[i] = pos;
        servos[i].write((int)(pos + 0.5));
      }
    }
  }
}

// ----------------------
// PROCESAMIENTO DE COMANDOS SERIAL
// ----------------------
void procesarComandos() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    if (input.startsWith("A,")) {
      // Comando global: "A,angle1,angle2,...,angle6,velocidad\n"
      cmdGlobal(input);
    } else if (input.startsWith("S,")) {
      // Comando individual: "S,servo_num,angle\n"
      cmdIndividual(input);
    } else {
      // Comandos para el motor de la banda
      if (input == "P") {
        motorActivo = true;
        Serial.println("MOTOR: START");
      } else if (input == "S") {
        motorActivo = false;
        Serial.println("MOTOR: STOP");
      } else if (input == "D") {
        direccionDerecha = true;
        digitalWrite(dirPin, HIGH);
        Serial.println("MOTOR: DERECHA");
      } else if (input == "I") {
        direccionDerecha = false;
        digitalWrite(dirPin, LOW);
        Serial.println("MOTOR: IZQUIERDA");
      }
    }
  }
}

void cmdGlobal(String cmd) {
  // Se espera: "A,angle1,angle2,...,angle6,velocidad\n"
  cmd = cmd.substring(2); // Quitar el "A,"
  float angles[6];
  uint8_t newSpeed;
  
  char *token = strtok((char*)cmd.c_str(), ",");
  for (int i = 0; i < 6; i++) {
    if (!token) return;
    angles[i] = constrain(atof(token), 0.0, 180.0);
    token = strtok(NULL, ",");
  }
  newSpeed = token ? constrain(atoi(token), 1, 100) : servoSpeed;
  servoSpeed = newSpeed;
  
  for (int i = 0; i < 6; i++) {
    iniciarMovimiento(i, angles[i]);
  }
  Serial.println("OK: MOVIMIENTO GLOBAL");
}

void cmdIndividual(String cmd) {
  // Se espera: "S,servo_num,angle\n"
  cmd = cmd.substring(2);
  int servoNum = cmd.substring(0, cmd.indexOf(',')).toInt();
  float angle = cmd.substring(cmd.indexOf(',') + 1).toFloat();
  
  if (servoNum >= 1 && servoNum <= 6) {
    iniciarMovimiento(servoNum - 1, constrain(angle, 0.0, 180.0));
    Serial.print("OK: SERVO ");
    Serial.println(servoNum);
  }
}

void actualizarBanda() {
  if (motorActivo && (micros() - lastStepTime >= stepDelay)) {
    digitalWrite(stepPin, !digitalRead(stepPin));
    lastStepTime = micros();
  }
}

// ----------------------
// CONFIGURACIÓN INICIAL
// ----------------------
void setup() {
  Serial.begin(9600);
  
  // Inicializar servos a 90°
  for (int i = 0; i < 6; i++) {
    servos[i].attach(servoPins[i]);
    servos[i].write(90);
  }
  
  // Configurar pines del motor
  pinMode(dirPin, OUTPUT);
  pinMode(stepPin, OUTPUT);
  digitalWrite(dirPin, direccionDerecha);
  
  Serial.println("SISTEMA LISTO");
}

void loop() {
  procesarComandos();
  actualizarMovimientos();
  actualizarBanda();
}