"""Java adapter builder."""

import shutil
import urllib.request
from pathlib import Path

from ..base import AdapterBuilder, BuildError
from ..metadata import create_and_write_metadata


class JavaAdapterBuilder(AdapterBuilder):
    """Builder for Java debug adapter."""

    def __init__(self, versions: dict, platform_name: str, arch: str):
        super().__init__(versions, platform_name, arch)
        self._built_dist_dir = None

    @property
    def adapter_name(self) -> str:
        """Return the name of this adapter."""
        return "java"

    def get_adapter_config(self) -> dict:
        """Get adapter configuration from versions.json."""
        return self.versions["adapters"]["java"]

    def clone_repository(self) -> Path:
        """Not used for Java adapter - we download from Maven Central.

        Returns
        -------
        Path
            Not applicable - raises NotImplementedError

        Raises
        ------
        NotImplementedError
            This method is not used for Java adapter
        """
        msg = "Java adapter downloads from Maven Central, cloning not required"
        raise NotImplementedError(msg)

    def _download_java_debug_jar(self, dist_dir: Path, version: str) -> Path:
        """Download java-debug.jar from Maven Central.

        Parameters
        ----------
        dist_dir : Path
            Distribution directory to download to
        version : str
            Version of java-debug to download

        Returns
        -------
        Path
            Path to downloaded JAR file
        """
        # Maven Central download URL
        base_url = "https://repo1.maven.org/maven2"
        group_path = "com/microsoft/java"
        artifact = "com.microsoft.java.debug.plugin"
        jar_name = f"{artifact}-{version}.jar"
        download_url = f"{base_url}/{group_path}/{artifact}/{version}/{jar_name}"

        jar_path = dist_dir / "java-debug.jar"

        print(f"Downloading {jar_name} from Maven Central...")
        print(f"URL: {download_url}")

        # Download JAR using urllib (no external dependencies)
        try:
            urllib.request.urlretrieve(download_url, jar_path)  # noqa: S310
        except Exception as e:
            msg = f"Failed to download JAR from Maven Central: {e}"
            raise BuildError(msg) from e

        file_size = jar_path.stat().st_size
        print(f"Downloaded {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")

        return jar_path

    def _download_jdtls(self, dist_dir: Path, jdtls_version: str) -> Path:
        """Download and extract Eclipse JDT Language Server.

        Parameters
        ----------
        dist_dir : Path
            Distribution directory to extract to
        jdtls_version : str
            Version of JDT LS to download (e.g., '1.51.0-202509121646')

        Returns
        -------
        Path
            Path to extracted jdtls directory
        """
        jdtls_dir = dist_dir / "jdtls"
        jdtls_dir.mkdir(exist_ok=True)

        # Eclipse download URL
        download_url = (
            f"https://download.eclipse.org/jdtls/snapshots/"
            f"jdt-language-server-{jdtls_version}.tar.gz"
        )

        tarball = dist_dir / "jdtls.tar.gz"

        print(f"Downloading JDT LS {jdtls_version}...")
        print(f"URL: {download_url}")

        try:
            urllib.request.urlretrieve(download_url, tarball)  # noqa: S310
        except Exception as e:
            msg = f"Failed to download JDT LS from Eclipse: {e}"
            raise BuildError(msg) from e

        tarball_size = tarball.stat().st_size
        print(f"Downloaded {tarball_size:,} bytes ({tarball_size / 1024 / 1024:.1f} MB)")

        print("Extracting JDT LS...")
        self.run_command([
            "tar", "-xzf", str(tarball), "-C", str(jdtls_dir),
        ])

        # Clean up tarball
        tarball.unlink()

        # Verify essential directories exist
        plugins_dir = jdtls_dir / "plugins"
        if not plugins_dir.exists():
            msg = "JDT LS extraction failed: plugins/ directory not found"
            raise BuildError(msg)

        features_dir = jdtls_dir / "features"
        if not features_dir.exists():
            msg = "JDT LS extraction failed: features/ directory not found"
            raise BuildError(msg)

        print(f"JDT LS extracted successfully to {jdtls_dir}")
        return jdtls_dir

    def build(self) -> Path:
        """Download pre-built JAR and JDT LS from official sources.

        The Java debug plugin is published to Maven Central, and JDT LS
        is published to Eclipse downloads. This avoids Maven/Tycho build
        complexity and provides a complete debugging solution.

        Returns
        -------
        Path
            Path to the built distribution directory
        """
        config = self.get_adapter_config()
        version = config["version"]
        jdtls_version = config.get("jdtls_version")

        if not jdtls_version:
            msg = "jdtls_version not found in versions.json for java adapter"
            raise BuildError(msg)

        # Create distribution directory
        dist_dir = self.build_dir / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)

        # Download java-debug.jar
        self._download_java_debug_jar(dist_dir, version)

        # Download JDT LS
        self._download_jdtls(dist_dir, jdtls_version)

        self._built_dist_dir = dist_dir
        return dist_dir

    def package(self) -> Path:
        """Package the Java adapter with JDT LS.

        Returns
        -------
        Path
            Path to the packaged adapter tarball
        """
        # Use the already built dist_dir if available
        dist_dir = self._built_dist_dir if self._built_dist_dir else self.build()
        config = self.get_adapter_config()
        version = config["version"]

        # Java adapter is universal (platform-independent)
        adapter_name = f"java-{version}-universal"
        package_dir = self.dist_dir / adapter_name
        package_dir.mkdir(exist_ok=True)

        # Copy java-debug.jar
        jar_file = dist_dir / "java-debug.jar"
        if not jar_file.exists():
            msg = f"java-debug.jar not found in {dist_dir}"
            raise BuildError(msg)
        shutil.copy2(jar_file, package_dir / "java-debug.jar")

        # Copy jdtls directory
        jdtls_src = dist_dir / "jdtls"
        if not jdtls_src.exists():
            msg = f"jdtls directory not found in {dist_dir}"
            raise BuildError(msg)

        jdtls_dst = package_dir / "jdtls"
        print("Copying JDT LS directory to package...")
        shutil.copytree(jdtls_src, jdtls_dst)

        # Create metadata.json with adapter information
        create_and_write_metadata(
            adapter_name="java",
            platform="universal",
            arch="universal",
            output_directory=package_dir,
            binary_identifier="java-debug.jar",
        )

        # Create tarball
        tarball_path = self.dist_dir / f"{adapter_name}.tar.gz"
        print(f"Creating tarball: {tarball_path}")
        self.run_command([
            "tar", "-czf", str(tarball_path),
            "-C", str(self.dist_dir), adapter_name,
        ])

        # Clean up package directory
        shutil.rmtree(package_dir)

        tarball_size = tarball_path.stat().st_size
        print(f"Package size: {tarball_size:,} bytes ({tarball_size / 1024 / 1024:.1f} MB)")

        return tarball_path
