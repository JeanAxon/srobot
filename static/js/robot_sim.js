/* =========================================================
   static/js/robot_sim.js
   ---------------------------------------------------------
   Motor de simulación 3D (Three.js).
   Se encarga de dibujar el "Gemelo Digital" del robot.
   No sabe nada de API ni de HTML, solo recibe ángulos y dibuja.
   ========================================================= */

class RobotSimulation {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Contenedor 3D '${containerId}' no encontrado.`);
            return;
        }

        // Variables de Three.js
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.robotParts = null; // Referencias a las articulaciones móviles
        this.workspacePoints = null; // Nube de puntos

        this.init();
    }

    init() {
        // 1. Configuración Básica (Escena, Cámara, Renderer)
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf8fafc); // Fondo gris muy claro (moderno)

        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 50);
        this.camera.position.set(1.2, 1.2, 1.2);
        this.camera.lookAt(new THREE.Vector3(0, 0.5, 0));

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.shadowMap.enabled = true;
        this.container.appendChild(this.renderer.domElement);

        // Controles de Cámara (OrbitControls)
        // Nota: OrbitControls debe estar cargado en el HTML antes que este script
        if (THREE.OrbitControls) {
            const controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            controls.target.set(0, 0.5, 0);
            controls.update();
        }

        // 2. Iluminación
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
        hemiLight.position.set(0, 20, 0);
        this.scene.add(hemiLight);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(3, 10, 5);
        dirLight.castShadow = true;
        this.scene.add(dirLight);

        // 3. Entorno (Suelo y Ejes)
        const gridHelper = new THREE.GridHelper(20, 40, 0x94a3b8, 0xe2e8f0);
        gridHelper.position.y = 0.001;
        this.scene.add(gridHelper);

        const axesHelper = new THREE.AxesHelper(0.5);
        this.scene.add(axesHelper);

        // 4. Construir el Robot
        this.robotParts = this.createRobotModel();

        // 5. Iniciar Loop de Animación
        this.animate();

        // 6. Listener para Resize
        window.addEventListener('resize', () => this.onResize());
    }

    createRobotModel() {
        const dims = {
            baseHeight: 0.1, baseDiameter: 0.12,
            shoulderLength: 0.15, shoulderThickness: 0.06,
            elbowLength: 0.14, elbowThickness: 0.06,
            wristLength: 0.13, wristThickness: 0.05
        };

        // Materiales
        const metalMaterial = new THREE.MeshPhysicalMaterial({ color: 0x64748b, metalness: 0.6, roughness: 0.4 });
        const accentMaterial = new THREE.MeshPhysicalMaterial({ color: 0x0ea5e9, metalness: 0.5, roughness: 0.5 });
        const jointMaterial = new THREE.MeshPhysicalMaterial({ color: 0xf59e0b, metalness: 0.8, roughness: 0.2 });

        const robotGroup = new THREE.Group();

        // --- Base ---
        const baseGeo = new THREE.CylinderGeometry(dims.baseDiameter/2, dims.baseDiameter/2, dims.baseHeight, 32);
        const baseMesh = new THREE.Mesh(baseGeo, metalMaterial);
        baseMesh.position.y = dims.baseHeight / 2;
        
        const baseGroup = new THREE.Group();
        baseGroup.add(baseMesh);

        // Junta Base
        const jointGeo = new THREE.SphereGeometry(0.015, 32, 32);
        const baseJoint = new THREE.Mesh(jointGeo, jointMaterial);
        baseJoint.position.y = dims.baseHeight;
        baseGroup.add(baseJoint);
        robotGroup.add(baseGroup);

        // --- Hombro ---
        const shoulderGroup = new THREE.Group();
        shoulderGroup.position.y = dims.baseHeight;
        baseGroup.add(shoulderGroup);

        const shoulderGeo = new THREE.BoxGeometry(dims.shoulderThickness, dims.shoulderLength, dims.shoulderThickness);
        const shoulderMesh = new THREE.Mesh(shoulderGeo, accentMaterial);
        shoulderMesh.position.y = dims.shoulderLength / 2;
        shoulderGroup.add(shoulderMesh);

        const shoulderJoint = new THREE.Mesh(jointGeo, jointMaterial);
        shoulderJoint.position.y = dims.shoulderLength;
        shoulderGroup.add(shoulderJoint);

        // --- Codo ---
        const elbowGroup = new THREE.Group();
        elbowGroup.position.y = dims.shoulderLength;
        shoulderGroup.add(elbowGroup);

        const elbowGeo = new THREE.BoxGeometry(dims.elbowThickness, dims.elbowLength, dims.elbowThickness);
        const elbowMesh = new THREE.Mesh(elbowGeo, metalMaterial);
        elbowMesh.position.y = dims.elbowLength / 2;
        elbowGroup.add(elbowMesh);

        const elbowJoint = new THREE.Mesh(jointGeo, jointMaterial);
        elbowJoint.position.y = dims.elbowLength;
        elbowGroup.add(elbowJoint);

        // --- Muñeca (Vertical) ---
        const wristGroup = new THREE.Group();
        wristGroup.position.y = dims.elbowLength;
        elbowGroup.add(wristGroup);

        const wristGeo = new THREE.BoxGeometry(dims.wristThickness, dims.wristLength, dims.wristThickness);
        const wristMesh = new THREE.Mesh(wristGeo, accentMaterial);
        wristMesh.position.y = dims.wristLength / 2;
        wristGroup.add(wristMesh);

        const wristJoint = new THREE.Mesh(jointGeo, jointMaterial);
        wristJoint.position.y = dims.wristLength;
        wristGroup.add(wristJoint);

        // --- Gripper (Base y Dedos) ---
        const gripperBaseGeo = new THREE.BoxGeometry(0.06, 0.02, 0.06);
        const gripperBase = new THREE.Mesh(gripperBaseGeo, metalMaterial);
        gripperBase.position.y = 0.01;
        wristJoint.add(gripperBase);

        const gripperGroup = new THREE.Group(); // Este rota (Muñeca Rotación)
        gripperGroup.position.y = 0.01;
        gripperBase.add(gripperGroup);

        // Pinzas (Izquierda y Derecha)
        const gripperWidth = 0.04, gripperHeight = 0.08, gripperDepth = 0.03;
        const jawGeo = new THREE.BoxGeometry(gripperWidth, gripperHeight, gripperDepth);
        jawGeo.translate(0, gripperHeight/2, 0); // Ajuste de pivote
        const gripperMaterial = new THREE.MeshPhysicalMaterial({ color: 0xea580c });

        const gripperRight = new THREE.Mesh(jawGeo, gripperMaterial);
        gripperRight.position.set(0.03, 0, 0);
        gripperGroup.add(gripperRight);

        const gripperLeft = new THREE.Mesh(jawGeo, gripperMaterial);
        gripperLeft.position.set(-0.03, 0, 0);
        gripperGroup.add(gripperLeft);

        // Sombras
        robotGroup.traverse(child => {
            if(child.isMesh) { child.castShadow = true; child.receiveShadow = true; }
        });

        this.scene.add(robotGroup);

        // Retornamos referencias para poder moverlas después
        return { baseGroup, shoulderGroup, elbowGroup, wristGroup, gripperGroup, gripperRight, gripperLeft };
    }

    /**
     * Actualiza la posición visual del robot basada en los servos.
     * @param {Array} servos - [S1, S2, S3, S4, S5, S6] (Valores 0-180)
     */
    updateAngles(servos) {
        if (!this.robotParts) return;

        // Conversión Grados -> Radianes
        // La lógica original restaba 90 a todo.
        const degToRad = (deg) => THREE.Math.degToRad(deg - 90);

        this.robotParts.baseGroup.rotation.y     = degToRad(servos[0]);
        this.robotParts.shoulderGroup.rotation.x = degToRad(servos[1]);
        this.robotParts.elbowGroup.rotation.x    = degToRad(servos[2]);
        
        // Nota: En tu código original, el servo 4 (Muñeca V) tenía un signo negativo.
        this.robotParts.wristGroup.rotation.x    = -degToRad(servos[3]); 
        
        this.robotParts.gripperGroup.rotation.y  = degToRad(servos[4]);

        // Animación Pinzas (Gripper)
        // Servo 6: 90 (Abierto) -> 120 (Cerrado) aprox.
        // Mapeamos visualmente para que se muevan.
        const valGripper = servos[5];
        // Rango de movimiento visual: 0.03 (abierto) a 0.005 (cerrado)
        // Asumiendo rango servo 90-180 donde 180 es cerrado.
        // Ajuste heurístico basado en tu código original:
        const offsetOpen = 0.03;
        // Si 90 es abierto y 180 cerrado -> factor (180 - val) / 90
        const factor = Math.max(0, (180 - valGripper) / 90); 
        const offset = offsetOpen * factor;

        this.robotParts.gripperRight.position.x = offset;
        this.robotParts.gripperLeft.position.x  = -offset;
    }

    /**
     * Muestra/Oculta la nube de puntos del área de trabajo.
     * @param {Array} points - Lista de objetos {x,y,z}
     */
    toggleWorkspace(points) {
        if (this.workspacePoints) {
            // Si ya existe, lo borramos (Toggle OFF)
            this.scene.remove(this.workspacePoints);
            this.workspacePoints = null;
        } else if (points && points.length > 0) {
            // Si no existe, lo creamos (Toggle ON)
            const vertices = [];
            points.forEach(p => vertices.push(p.x, p.y, p.z));
            
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
            const material = new THREE.PointsMaterial({ color: 0xffff00, size: 0.015 });
            
            this.workspacePoints = new THREE.Points(geometry, material);
            this.scene.add(this.workspacePoints);
        }
    }

    onResize() {
        if (!this.camera || !this.renderer || !this.container) return;
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }
}