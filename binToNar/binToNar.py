# -*- coding: utf-8 -*-

__author__ = 'markj'

from subprocess import call
import platform
from os import makedirs
from os import path
import shutil

import click

from binToNar import narGlobals as nar
from binToNar.linuxLib import LinuxLib
from binToNar.windowsLib import WindowsLib
from binToNar.pom import Pom

verbosity = 0


@click.command()
@click.option("-l", "--libpath", type=click.Path(exists=True), help="The path to the library you wish to create a NAR from.", prompt=True)
@click.option("-i", "--includepath", type=click.Path(exists=True),
              help="The path to the library includes, that is, the non-architecture specific headers.", prompt=True)
@click.option("-p", "--pompath", type=click.Path(exists=True),
              help="The pom file that describes this project. Auto-generation not currently supported.", prompt=True)
@click.option("-g", "--groupid", help="Unique identifier for your project following package name rules.", prompt=True)
@click.option("-a", "--artifactid", help="The name of the library.", prompt=True)
@click.option("-vr", "--version", help="The version of the library.", prompt=True)
@click.option("-ar", "--architecture", type=click.Choice(nar.ARCH_TYPES), help="The architecture the library was built on.", prompt=True)
@click.option("-o", "--os", type=click.Choice(nar.OS_TYPES), help="The operating system the library was built on.", prompt=True)
@click.option("-ln", "--linker", type=click.Choice(nar.LINKER_TYPES), help="The linker the library was built with.", prompt=True)
@click.option("-t", "--type", type=click.Choice(nar.LIB_TYPES), help="The type of library.", prompt=True)
@click.option("-in", "--install", default=False, is_flag=True, help="Whether to install the resultant NARs into the local maven repo.")
@click.option("-d", "--deploy", nargs=2, help="Whether to deploy the resultant NARs into a given repo. Requires the repo URL and the server id")
@click.option("--ext", help="If your library has a non-standard filename extension you can provide it here.")
@click.option("-v", "--verbose", count=True, help="Verbosity of the utility. Accepts one or to repeats for two levels of output, e.g. -v or -vv")
@click.argument("outdir", type=click.Path(exists=True))
def enterCommandLine(libpath, includepath, pompath, groupid, artifactid, version, architecture, os, linker, type, install, deploy, ext, verbose, outdir):
    """
    Wraps an existing native library in a NAR package for use with the nar plugin in the maven build system.

    OUTDIR is the location you wish to generate the files.

    """
    click.secho("-----------------------", bold=True, fg="green")
    click.secho("Binary to NAR generator", bold=True, fg="green")
    click.secho("-----------------------", bold=True, fg="green")

    global verbosity
    verbosity = verbose

    aol = createAol(architecture, os, linker)

    if os == "Linux":
        lib = LinuxLib(libpath, version, type, ext)
    else:
        lib = WindowsLib(libpath, version, type, ext)

    pom = Pom(pompath, groupid, artifactid, version, outdir)

    printPlan(aol, lib, pom, install, deploy, outdir)

    if click.confirm("\nShall we get on with it?", default=True):
        click.secho("Ok, sit back and relax!")
        createNar(lib, aol, groupid, artifactid, architecture, os, linker, outdir)
        createNoArchNar(lib, includepath, outdir)
        createLibNar(lib, aol, outdir)
        if install:
            installNar(pom, lib, aol, outdir)
        if deploy:
            deployNar(pom, lib, aol, outdir, deploy[0], deploy[1])

    click.secho("We're done!", bold=True, fg="green")


def printPlan(aol, lib, pom, install, deploy, outdir):
    click.secho("Library details:", bold=True)
    click.secho("  ├── Name is " + lib.libName)
    click.secho("  ├── Type is " + lib.type)
    click.secho("  ├── AOL is " + aol)
    click.secho("  └── Version is " + lib.version)
    click.secho("Execution plan:", bold=True)
    click.secho("  ├── 1. Create base NAR file called " + lib.createNarFileName())
    click.secho("  ├── 2. Create non-architecture specific NAR file called " + lib.createNarNoArchFileName())
    click.secho("  ├── 3. Create shared lib NAR file called " + lib.createNarSharedLibFileName(aol))
    if not install:
        click.secho("  └── 4. Use the pom file " + pom.path)
    else:
        click.secho("  ├── 4. Use the pom file " + pom.path)
        click.secho("  └── 5. Install the artefacts into the local repository")

    click.echo()
    click.secho("Files will be generated in ", nl=False)
    click.secho(outdir, fg="blue", bold=True)

    if install:
        click.echo("The NARS", nl=False)
        click.secho(" WILL ", nl=False, bold=True, fg="blue")
        click.echo("be installed into the local repo and available for use immediately.")
    else:
        click.echo("The NARS will", nl=False)
        click.secho(" NOT ", nl=False, bold=True, fg="red")
        click.echo("be installed into the local repo and therefore not available for use.")


def createAol(architecture, os, linker):
    if (linker == "g++"):
        return architecture + "-" + os + "-gpp"
    else:
        return architecture + "-" + os + "-" + linker


def createNar(lib, aol, groupId, artifactId, arch, operatingSystem, linker, outdir):
    propertiesPath = path.join(outdir, "META-INF", "nar", groupId, artifactId)
    makedirs(propertiesPath)

    narProps = open(path.join(propertiesPath, "nar.properties"), 'w')

    narProps.write("output=" + lib.libName + "-" + lib.version + "\n")
    narProps.write("nar.noarch=" + groupId + "\:" + artifactId + "\:nar\:noarch\n")
    narProps.write(aol + ".output=" + lib.libName + "\n")
    narProps.write(aol + ".libs.binding=" + lib.type + "\n")
    narProps.write("libs.binding=" + lib.type + "\n")
    narProps.write("nar.shared=" + groupId + "\:" + artifactId + "\:nar\:${aol}-" + lib.type + "\n")
    narProps.close()

    createJar(lib.createNarFileName(), "META-INF/", outdir)

    shutil.rmtree(path.join(outdir, "META-INF/"))


def createNoArchNar(lib, includepath, outdir):
    allExceptHeaders = lambda srcDir, files: [f for f in files if path.isfile(path.join(srcDir, f)) and f[-2:] != ".h" and f[-4:] != ".hpp"]
    includeTargetPath = path.join(outdir, "include")
    shutil.copytree(includepath, includeTargetPath, ignore=allExceptHeaders)
    createJar(lib.createNarNoArchFileName(), "include/", outdir)
    shutil.rmtree(includeTargetPath)


def createLibNar(lib, aol, outdir):
    libPath = path.join(outdir, "lib", aol, lib.type)
    makedirs(libPath)
    shutil.copy(lib.libPath, libPath)
    createJar(lib.createNarSharedLibFileName(aol), "lib/", outdir)
    shutil.rmtree(path.join(outdir, "lib"))

def createJar(fileName, files, outdir):
    if verbosity > 1:
        jarCommand = ["jar", "-cvfM", path.join(outdir, fileName), "-C", outdir, files]
        click.secho(" ".join(jarCommand), fg='magenta')
    else:
        jarCommand = ["jar", "-cfM", path.join(outdir, fileName), "-C", outdir, files]
    call(jarCommand)


def installNar(pom, lib, aol, outdir):
    narInstallCmd = [
        "mvn",
        "\"org.apache.maven.plugins:maven-install-plugin:2.5.2::install-file\"",
        "\"-Dfile=" + lib.createNarFileName() + "\"",
        "\"-Dtype=nar" + "\"",
        "\"-DgroupId=" + pom.groupId  + "\"",
        "\"-DartifactId=" + pom.artifactId  + "\"",
        "\"-Dversion=" + pom.version + "\"",
        "\"-Dpackaging=nar\"",
        "\"-DgeneratePom=false\""
    ]
    noarchInstallCmd = [
        "mvn", "org.apache.maven.plugins:maven-install-plugin:2.5.2::install-file",
        "\"-Dfile=" + lib.createNarNoArchFileName() + "\"",
        "\"-Dpackaging=nar\"",
        "\"-DgeneratePom=false\"",
        "\"-Dclassifier=" + nar.NAR_NOARCH_QUALIFIER  + "\"",
        "\"-DpomFile=" + pom.path + "\""
    ]
    libInstallCmd = [
        "mvn", "org.apache.maven.plugins:maven-install-plugin:2.5.2::install-file",
        "\"-Dfile=" + lib.createNarSharedLibFileName(aol) + "\"",
        "\"-Dpackaging=nar\"",
        "\"-DgeneratePom=false\"",
        "\"-Dclassifier=" + aol + "-" + lib.type + "\"",
        "\"-DpomFile=" + pom.path + "\""
    ]

    click.secho("Installing NAR file.", fg="green")
    click.secho(" ".join(narInstallCmd), fg="cyan")
    call(narInstallCmd, shell=isShellRequired(), cwd=outdir)

    click.secho("Installing noarch NAR file.", fg="green")
    click.secho(" ".join(noarchInstallCmd), fg="cyan")
    call(noarchInstallCmd, shell=isShellRequired(), cwd=outdir)

    click.secho("Installing lib NAR file.", fg="green")
    click.secho(" ".join(libInstallCmd), fg="cyan")
    call(libInstallCmd, shell=isShellRequired(), cwd=outdir)


def deployNar(pom, lib, aol, outdir, repoUrl, serverId):
    narDeployCmd = [
        "mvn",
        "\"org.apache.maven.plugins:maven-deploy-plugin:2.8.2:deploy-file\"",
        "\"-Dfile=" + lib.createNarFileName() + "\"",
        "\"-Dtype=nar" + "\"",
        "\"-DgroupId=" + pom.groupId  + "\"",
        "\"-DartifactId=" + pom.artifactId  + "\"",
        "\"-Dversion=" + pom.version + "\"",
        "\"-Dpackaging=nar\"",
        "\"-DgeneratePom=false\"",
        "\"-DrepositoryId=" + serverId + "\"",
        "\"-Durl=" + repoUrl + "\""
    ]
    noarchDeployCmd = [
        "mvn",
        "\"org.apache.maven.plugins:maven-deploy-plugin:2.8.2:deploy-file\"",
        "\"-Dfile=" + lib.createNarNoArchFileName() + "\"",
        "\"-Dpackaging=nar\"",
        "\"-DgeneratePom=false\"",
        "\"-Dclassifier=" + nar.NAR_NOARCH_QUALIFIER  + "\"",
        "\"-DpomFile=" + pom.path + "\"",
        "\"-DrepositoryId=" + serverId + "\"",
        "\"-Durl=" + repoUrl + "\""
    ]
    libDeployCmd = [
        "mvn",
        "\"org.apache.maven.plugins:maven-deploy-plugin:2.8.2:deploy-file\"",
        "\"-Dfile=" + lib.createNarSharedLibFileName(aol) + "\"",
        "\"-Dpackaging=nar\"",
        "\"-DgeneratePom=false\"",
        "\"-Dclassifier=" + aol + "-" + lib.type + "\"",
        "\"-DpomFile=" + pom.path + "\"",
        "\"-DrepositoryId=" + serverId + "\"",
        "\"-Durl=" + repoUrl + "\""
    ]

    click.secho("Deploying NAR file.", fg="green")
    click.secho(" ".join(narDeployCmd), fg="cyan")
    call(narDeployCmd, shell=isShellRequired(), cwd=outdir)

    click.secho("Deploying noarch NAR file.", fg="green")
    click.secho(" ".join(noarchDeployCmd), fg="cyan")
    call(noarchDeployCmd, shell=isShellRequired(), cwd=outdir)

    click.secho("Deploying lib NAR file.", fg="green")
    click.secho(" ".join(libDeployCmd), fg="cyan")
    call(libDeployCmd, shell=isShellRequired(), cwd=outdir)


def isShellRequired():
    """
    :return: True if the shell is required to execute Maven
    """
    if platform.system() == "Windows":
        return True
    else:
        return False
