
## One time setup

### certificate generation

The root CA certificate (`rootCA.pem`) used to sign the server certificates is already available in `setup_files/rootCA.pem`. You can use this certificate directly.

Push the certificate to the Android device:

```bash
adb push setup_files/rootCA.pem /sdcard/Download/
```

Now, install the certificate in the device. Open **Settings** and search for **CA Certificate**. Select the `rootCA.pem` file pushed previously.

If you want to generate your own certificates instead, you can use `mkcert`:

```bash
mkcert -install
mkcert a.com b.com localhost 127.0.0.1
```

To find the certification authority certificate file, run:

```bash
mkcert -CAROOT
```

Then push it to the device:

```bash
adb push /path/to/authority/rootCA.pem /sdcard/Download/
```

### Password manager entries

For each password manager to test, create these credentials:

Website: a.com
Username: a@mail.com
Password: aaaapassword

Website: b.com
Username: b@mail.com
Password: bbbbpassword

## Running the server

To start the server, run:

```bash
./run_server.sh
```

This script will first execute the network setup, then start the orchestrator on ports 80 (HTTP) and 443 (HTTPS).

Once the orchestrator is running, use the following commands:

1. **Set the browser** to test:
   ```
   browser <package_name>
   ```

2. **Enter test mode**:
   ```
   test
   ```

3. **Run tests**: Press **Enter** to proceed to the next test. The orchestrator will automatically advance through tests 0-9.

## Setup script explaination

This section explains what the setup scripts do, it is not necessary to read it to run the server.

### Networking

The `network_setup.sh` script performs multiple things.

#### Making the certifcate a **System credential**

In the one time setup the certification authority certificate was installed as a **User credential**. Most of the browsers only use **System credentials**. 

To make your certificate a System certificate, follow these steps (the script.sh was written by Tim Perry from [HTTP Toolkit](https://httptoolkit.com/blog/android-14-install-system-ca-certificate/)):

```bash
adb push setup_files/script.sh /data/local/tmp
adb shell
```

Now in the device's shell:

```bash
su
cd /data/local/tmp
chmod +x script.sh
./script.sh
```

At this point, the custom certificate should appear under **System credentials**

#### Domain resolution

The device needs to resolve `a.com` and `b.com` to `127.0.0.1`. To do so, you can change the content of the `/system/etc/hosts` file. The `system` is write-only only so you need to perform some additional steps to overwrite the file, in a similar fashion on how the script used in the previous section does it.

In the device, create a temporary directory and copy the content of `/system/etc/` into it:

```bash
su
mkdir /data/local/tmp/etc-tmp
cp -r /system/etc/. /data/local/tmp/etc-tmp/
```

Add the following lines to the `/data/local/tmp/etc-tmp/hosts` file:

```
127.0.0.1	a.com
127.0.0.1	b.com
```

Now run these commands: 

```bash
mount -t tmpfs tmpfs /system/etc/
cp -r /data/local/tmp/etc-tmp/. /system/etc/

chown root:root /system/etc/*
chmod 644 /system/etc/*
chcon u:object_r:system_file:s0 /system/etc/*
```

At this point, the devices should correctly map `a.com` and `b.com` to `127.0.0.1`.

#### Adb reverse

 Now you need to map the device's ports `8080`, `8443` and `8081` of `127.0.0.1` to your computer port `80` and `443` of `127.0.0.1`. To do so, run:

```bash
adb reverse tcp:8080 tcp:80 
adb reverse tcp:8443 tcp:443
adb reverse tcp:8081 tcp:443
```
Then you should map the device's ports `80` and `443` to the devices's port `8080`,`8443`. We need this loop because we cannot use adb reverse to directly map device's `80` or `443` to computer's `80` or `443`. But with this loop we achieve the same result.
